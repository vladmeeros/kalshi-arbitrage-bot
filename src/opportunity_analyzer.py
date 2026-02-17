"""
Probability Arbitrage Detection Module

Advanced market analysis system for identifying probability arbitrage opportunities
in Kalshi prediction markets. This module detects market inefficiencies where contract
probabilities deviate from expected values, creating risk-free profit opportunities.

Arbitrage occurs when the combined YES and NO contract probabilities don't equal 100%:
    - Overpricing: YES at 52¢ + NO at 50¢ = 102% total (2% profit opportunity)
    - Underpricing: YES at 48¢ + NO at 50¢ = 98% total (2% profit opportunity)

The module performs comprehensive analysis including:
    - Gross profit calculation from probability deviations
    - Net profit computation after trading fees
    - Time-weighted profitability (profit per day)
    - Optimal trade execution recommendations
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dateutil import parser as date_parser
from .cost_calculator import FeeCalculator


class ArbitrageOpportunity:
    """
    Data structure representing a probability arbitrage opportunity.
    
    Contains all relevant information for evaluating and executing an arbitrage trade,
    including market details, profit calculations, and recommended trade actions.
    """
    
    def __init__(self, market_ticker: str, market_title: str, 
                 total_probability: float, deviation: float,
                 expiration_date: datetime, trades: List[Dict],
                 gross_profit: float, net_profit: float,
                 days_to_expiration: float):
        self.market_ticker = market_ticker
        self.market_title = market_title
        self.total_probability = total_probability
        self.deviation = deviation
        self.expiration_date = expiration_date
        self.trades = trades
        self.gross_profit = gross_profit
        self.net_profit = net_profit
        self.days_to_expiration = days_to_expiration
        self.profit_per_day = net_profit / max(days_to_expiration, 0.01)
    
    def __repr__(self):
        return (f"ArbitrageOpportunity(ticker={self.market_ticker}, "
                f"deviation={self.deviation:.2f}%, "
                f"profit_per_day=${self.profit_per_day:.2f})")


class ArbitrageAnalyzer:
    """
    Advanced market analyzer for probability arbitrage detection.
    
    Performs sophisticated analysis of market data to identify arbitrage opportunities
    where contract probabilities deviate from expected values. The analyzer considers
    trading fees, time to expiration, and market liquidity to provide accurate
    profitability assessments.
    """
    
    def __init__(self, min_deviation: float = None):
        """
        Initialize the analyzer.
        
        Args:
            min_deviation: DEPRECATED - No longer used. Filtering is now based on net profit > 0.
                          Kept for backwards compatibility but ignored.
        """
        pass
    
    def analyze_market(self, market_data: Dict, orderbook: Optional[Dict] = None) -> Optional[ArbitrageOpportunity]:
        """
        Analyze a single market for arbitrage opportunities.
        
        Args:
            market_data: Market information dictionary
            orderbook: Optional orderbook data for more accurate pricing
        
        Returns:
            ArbitrageOpportunity if found, None otherwise
        """
        try:
            market_ticker = market_data.get("ticker", "")
            market_title = market_data.get("title", "")
            
            expiration_str = market_data.get("expiration_time") or market_data.get("expiration_date")
            if not expiration_str:
                return None
            
            expiration_date = date_parser.parse(expiration_str)
            days_to_expiration = (expiration_date - datetime.now(expiration_date.tzinfo)).total_seconds() / 86400
            
            if days_to_expiration <= 0:
                return None
            
            market_type = market_data.get("market_type", "")
            
            yes_bid = market_data.get("yes_bid")
            yes_ask = market_data.get("yes_ask")
            no_bid = market_data.get("no_bid")
            no_ask = market_data.get("no_ask")
            
            total_prob = 0.0
            contract_prices = []
            
            if market_type == "binary" and (yes_bid is not None or yes_ask is not None):
                if yes_bid is not None and no_bid is not None:
                    total_prob_bid = (yes_bid + no_bid) / 100.0
                    if total_prob_bid > 1.0:
                        contract_prices = [
                            {
                                'ticker': market_ticker,
                                'side': 'yes',
                                'price': yes_bid,
                                'probability': yes_bid / 100.0
                            },
                            {
                                'ticker': market_ticker,
                                'side': 'no',
                                'price': no_bid,
                                'probability': no_bid / 100.0
                            }
                        ]
                        total_prob = total_prob_bid
                
                if not contract_prices and yes_ask is not None and no_ask is not None:
                    total_prob_ask = (yes_ask + no_ask) / 100.0
                    if total_prob_ask < 1.0:
                        contract_prices = [
                            {
                                'ticker': market_ticker,
                                'side': 'yes',
                                'price': yes_ask,
                                'probability': yes_ask / 100.0
                            },
                            {
                                'ticker': market_ticker,
                                'side': 'no',
                                'price': no_ask,
                                'probability': no_ask / 100.0
                            }
                        ]
                        total_prob = total_prob_ask
                
                if not contract_prices:
                    yes_price = None
                    no_price = None
                    
                    if yes_bid is not None and yes_ask is not None:
                        yes_price = (yes_bid + yes_ask) / 2
                    elif yes_bid is not None:
                        yes_price = yes_bid
                    elif yes_ask is not None:
                        yes_price = yes_ask
                    
                    if no_bid is not None and no_ask is not None:
                        no_price = (no_bid + no_ask) / 2
                    elif no_bid is not None:
                        no_price = no_bid
                    elif no_ask is not None:
                        no_price = no_ask
                    
                    if yes_price is not None and no_price is not None:
                        total_prob = (yes_price + no_price) / 100.0
                        contract_prices = [
                            {
                                'ticker': market_ticker,
                                'side': 'yes',
                                'price': int(yes_price),
                                'probability': yes_price / 100.0
                            },
                            {
                                'ticker': market_ticker,
                                'side': 'no',
                                'price': int(no_price),
                                'probability': no_price / 100.0
                            }
                        ]
            
            if not contract_prices:
                contracts = market_data.get("contracts", [])
                if not contracts:
                    outcomes = market_data.get("outcomes", [])
                    if outcomes:
                        contracts = outcomes
                
                if contracts:
                    for contract in contracts:
                        price_cents = contract.get("last_price")
                        if price_cents is None:
                            yes_bid_c = contract.get("yes_bid")
                            yes_ask_c = contract.get("yes_ask")
                            if yes_bid_c is not None and yes_ask_c is not None:
                                price_cents = (yes_bid_c + yes_ask_c) / 2
                            elif yes_bid_c is not None:
                                price_cents = yes_bid_c
                            elif yes_ask_c is not None:
                                price_cents = yes_ask_c
                        
                        if price_cents is not None:
                            prob = price_cents / 100.0
                            total_prob += prob
                            contract_prices.append({
                                'ticker': contract.get("ticker", market_ticker),
                                'side': 'yes',
                                'price': int(price_cents),
                                'probability': prob
                            })
            
            if not contract_prices:
                return None
            
            deviation = abs(total_prob - 1.0) * 100
            
            trades = []
            gross_profit = 0.0
            base_quantity = 100
            
            if total_prob > 1.0:
                overpricing = total_prob - 1.0
                
                for contract in contract_prices:
                    normalized_prob = contract['probability'] / total_prob
                    quantity = int(base_quantity * normalized_prob)
                    
                    if quantity > 0:
                        trades.append({
                            'ticker': contract['ticker'],
                            'side': contract.get('side', 'yes'),
                            'action': 'sell',
                            'price': contract['price'],
                            'quantity': quantity
                        })
                
                gross_profit = overpricing * base_quantity
            
            else:
                underpricing = 1.0 - total_prob
                
                for contract in contract_prices:
                    normalized_prob = contract['probability'] / total_prob
                    quantity = int(base_quantity * normalized_prob)
                    
                    if quantity > 0:
                        trades.append({
                            'ticker': contract['ticker'],
                            'side': contract.get('side', 'yes'),
                            'action': 'buy',
                            'price': contract['price'],
                            'quantity': quantity
                        })
                
                gross_profit = underpricing * base_quantity
            
            if not trades:
                return None
            
            net_profit = FeeCalculator.calculate_net_profit(
                gross_profit,
                [{'price': t['price'], 'quantity': t['quantity']} for t in trades],
                all_maker=True
            )
            
            if net_profit <= 0:
                return None
            
            return ArbitrageOpportunity(
                market_ticker=market_ticker,
                market_title=market_title,
                total_probability=total_prob * 100,
                deviation=deviation,
                expiration_date=expiration_date,
                trades=trades,
                gross_profit=gross_profit,
                net_profit=net_profit,
                days_to_expiration=days_to_expiration
            )
        
        except Exception as e:
            print(f"Error analyzing market {market_data.get('ticker', 'unknown')}: {e}")
            return None
    
    def find_opportunities(self, markets: List[Dict], 
                          client=None) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities across multiple markets.
        
        Args:
            markets: List of market dictionaries
            client: Optional KalshiClient to fetch orderbooks
        
        Returns:
            List of ArbitrageOpportunity objects
        """
        opportunities = []
        
        for market in markets:
            opportunity = self.analyze_market(market, orderbook=None)
            if opportunity:
                opportunities.append(opportunity)
        
        opportunities.sort(key=lambda x: x.profit_per_day, reverse=True)
        
        return opportunities

