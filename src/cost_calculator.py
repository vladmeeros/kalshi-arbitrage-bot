"""
Trading Fee Calculator Module

Comprehensive fee calculation system for Kalshi contract trading. Provides accurate
fee estimation based on contract prices, order types, and trading volumes to ensure
realistic profit projections.

Kalshi Fee Structure:
    - Contracts near 50¢: ~3.5% fee (highest rate)
    - Contracts at extremes (0-5¢ or 95-100¢): ~1% fee (lowest rate)
    - Maker orders (limit orders): 50% fee discount
    - Taker orders (market orders): Full fee rate

This module enables precise profit calculations by accounting for all trading costs,
ensuring that identified opportunities reflect true net profitability.
"""
from typing import Dict, List


class FeeCalculator:
    """
    Professional fee calculation engine for Kalshi contract trading.
    
    Provides accurate fee estimation based on contract prices and order types,
    enabling precise profit calculations for trading strategies.
    """
    
    FEE_SCHEDULE = {
        (0, 5): 0.01,      # Very low prices: 1% fee
        (5, 10): 0.015,    # Low prices: 1.5% fee
        (10, 20): 0.02,    # Low-medium: 2% fee
        (20, 30): 0.025,   # Medium-low: 2.5% fee
        (30, 40): 0.03,    # Medium: 3% fee
        (40, 50): 0.035,   # Medium-high: 3.5% fee
        (50, 60): 0.035,   # Medium-high: 3.5% fee
        (60, 70): 0.03,    # Medium: 3% fee
        (70, 80): 0.025,   # Medium-low: 2.5% fee
        (80, 90): 0.02,    # Low-medium: 2% fee
        (90, 95): 0.015,   # High prices: 1.5% fee
        (95, 100): 0.01,
    }
    
    MAKER_FEE_MULTIPLIER = 0.5
    
    @classmethod
    def get_fee_rate(cls, price_cents: int, is_maker: bool = False) -> float:
        """
        Get the fee rate for a given contract price.
        
        Args:
            price_cents: Contract price in cents (0-100)
            is_maker: Whether this is a maker order (resting on book)
        
        Returns:
            Fee rate as a decimal (e.g., 0.035 for 3.5%)
        """
        price_cents = max(0, min(100, price_cents))
        
        base_fee = 0.035
        
        for (min_price, max_price), fee_rate in cls.FEE_SCHEDULE.items():
            if min_price <= price_cents < max_price:
                base_fee = fee_rate
                break
        
        return base_fee * cls.MAKER_FEE_MULTIPLIER if is_maker else base_fee
    
    @classmethod
    def calculate_fee(cls, price_cents: int, quantity: int, is_maker: bool = False) -> float:
        """
        Calculate the total fee for a trade.
        
        Args:
            price_cents: Contract price in cents
            quantity: Number of contracts
            is_maker: Whether this is a maker order
        
        Returns:
            Total fee in dollars
        """
        if quantity <= 0:
            return 0.0
        
        fee_rate = cls.get_fee_rate(price_cents, is_maker)
        return (price_cents * quantity * fee_rate) / 100.0
    
    @classmethod
    def calculate_net_profit(cls, gross_profit: float, trades: List[Dict], 
                            all_maker: bool = False) -> float:
        """
        Calculate net profit after fees for multiple trades.
        
        Args:
            gross_profit: Gross profit before fees
            trades: List of trade dicts with 'price' and 'quantity' keys
            all_maker: Whether all trades are maker orders
        
        Returns:
            Net profit after fees
        """
        total_fees = 0.0
        for trade in trades:
            fee = cls.calculate_fee(
                trade['price'],
                trade['quantity'],
                is_maker=all_maker
            )
            total_fees += fee
        
        return gross_profit - total_fees

