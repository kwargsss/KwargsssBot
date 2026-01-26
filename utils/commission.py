from config import ECO_CFG


class CommissionManager:
    def __init__(self):
        self.rates = ECO_CFG.get("commissions", {
            "pay": 0.05,
            "bank_withdraw": 0.02,
            "business_withdraw": 0.10
        })

    def calculate(self, amount: int, transaction_type: str, discount_factor: float = 0.0):
        base_rate = self.rates.get(transaction_type, 0.0)
        effective_rate = base_rate * (1.0 - discount_factor)
        
        if effective_rate < 0:
            effective_rate = 0.0
            
        fee = int(amount * effective_rate)

        if fee < 1 and effective_rate > 0 and amount > 10:
            fee = 1
            
        net_amount = amount - fee
        return fee, net_amount

commission_manager = CommissionManager()