from typing import (
    MutableMapping,
    Type,
)
from flask_restful import (
    Resource,
    reqparse,
    abort,
)
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    jwt_refresh_token_required,
    get_jwt_identity,
    get_raw_jwt
)
from models import (
    User,
    Payment,
    PaymentStatus
)
from extensions import (
    jwt,
    db,
)
from flask import request
import json
import requests
import urllib.parse
import urllib.request
from decimal import Decimal
import os

class BaseResource(Resource):
    __resources: MutableMapping[str, Type[Resource]] = {}

    def __init_subclass__(cls, *args, **kwargs):
        cls.__resources[cls.path] = cls
        super().__init_subclass__(*args, **kwargs)

    @classmethod
    def register(cls, api):
        for path, res in cls.__resources.items():
            api.add_resource(res, path)


class PaymentCreate(BaseResource):
    path = "/v1/create"

    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument(
            'amount', type=float, help='This field cannot be blank', required=True)

        self.auth_url = 'https://secure.snd.payu.com/pl/standard/user/oauth/authorize'
        self.auth_params = 'grant_type=client_credentials&client_id=%s&client_secret=%s'
        self.merch_id = '387263'
        self.merch_key = 'b336b8103e89ac3886189207d4cc7c1f'
        self.create_order_url = 'https://secure.snd.payu.com/api/v2_1/orders'

    def get_payu_auth_token(self):
        try:
            oauth_response = requests.post(self.auth_url, params=(self.auth_params % (self.merch_id, self.merch_key)))
            return oauth_response.json()['access_token']
        except:
            abort(500)

    def create_payment_data(self, user, amount, ip):
        return {
            "notifyUrl": os.environ['NOTIFY_URL'],
            "customerIp": ip,
            "merchantPosId": self.merch_id,
            "description": 'Quantum machine simulator worktime',
            "currencyCode": "PLN",
            "totalAmount": amount*100,
            "continueUrl": os.environ['SERVICE_URL'],
            "buyer": {
                "email": user.email,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "language": "pl"
            },
            "products": [
                {
                    "name": "Quantum machine simulator worktime",
                    "unitPrice": "1",
                    "quantity": amount
                },
            ]
        }

    @jwt_required
    def post(self):
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()
        if user is None:
            abort(403)

        data = self.parser.parse_args()
        amount = data['amount']

        token = self.get_payu_auth_token()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        r = requests.post(self.create_order_url,
                          json=self.create_payment_data(user, amount, request.remote_addr),
                          headers=headers,
                          allow_redirects=False)
        if r.status_code == 200 or r.status_code == 302:
            json = r.json()
            redirect_uri = json['redirectUri']
            order_id = json['orderId']

            payment = Payment(
                id=order_id,
                user_id=user.id,
                amount=amount,
                status=PaymentStatus.PENDING
            )

            try:
                db.session.add(payment)
                db.session.commit()
            except:
                abort(409)

            return {
                'uri': json['redirectUri']
            }
        else:
            abort(500)


class PayUNotify(BaseResource):
    path = "/v1/notify"

    def map_status(self, status):
        return {
            'COMPLETED': PaymentStatus.SUCCESS,
            'CANCELED': PaymentStatus.CANCELED,
            'PENING': PaymentStatus.PENDING
        }[status]

    def post(self):
        json = request.json

        order = None
        order_id = None
        status = None
        total_amount = None
        try:
            order = json['order']
            order_id = order['orderId']
            status = order['status']
            total_amount = Decimal(int(order['totalAmount']))/100
        except:
            abort(400)

        payment = Payment.query.filter_by(id=order_id).first()
        if payment is None:
            abort(403)

        new_status = self.map_status(status)
        if payment.status != new_status and payment.status == PaymentStatus.PENDING:
            payment.status = new_status

            if new_status == PaymentStatus.SUCCESS:
                user = User.query.filter_by(id=payment.user_id).first()
                if user is not None:
                    user.balance += total_amount

            db.session.commit()

        return { 'message': 'ok' }
