class Economy:
    def __init__(self, tax_rate):
        self.tax_rate = tax_rate
        self.total_tax_collected = 0.0

    def process_transaction(self, buyer, seller, amount):
        if buyer.wallet >= amount and amount > 0:
            tax = amount * self.tax_rate
            net_amount = amount - tax
            buyer.wallet -= amount
            seller.wallet += net_amount
            self.total_tax_collected += tax
            return True
        return False
        
    def apply_driver_fuel_tax(self, driver, amount=1.0):
        if driver.wallet >= amount:
            driver.wallet -= amount
            self.total_tax_collected += amount
