from liqpay import LiqPay
from config import LIQPAY_PUBLIC_KEY, LIQPAY_PRIVATE_KEY

def create_payment_url(amount, order_id):
    liqpay = LiqPay(LIQPAY_PUBLIC_KEY, LIQPAY_PRIVATE_KEY)
    params = {
        "action": "pay",
        "amount": amount,
        "currency": "UAH",
        "description": "Оплата за накрутку",
        "order_id": order_id,
        "version": "3",
        "sandbox": 1
    }
    return liqpay.cnb_url(params)
