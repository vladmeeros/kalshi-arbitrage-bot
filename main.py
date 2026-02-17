#!/usr/bin/env python3
"""
Kalshi Arbitrage Trading Bot

An intelligent trading system designed to identify and capitalize on arbitrage opportunities
in Kalshi prediction markets. The bot continuously monitors market conditions and identifies
two distinct types of profitable trading opportunities:

1. Probability Arbitrage: Markets where YES and NO contract probabilities don't sum to 100%,
   creating risk-free profit opportunities when properly executed.

2. Spread Trading: Orderbook inefficiencies where bid prices exceed ask prices, enabling
   instant profit through simultaneous buy and sell execution.

The system includes comprehensive fee calculations, risk management, and automated execution
capabilities to maximize profitability while maintaining safe trading practices.

Author: vladmeer
License: MIT
Repository: https://github.com/vladmeeros/kalshi-arbitrage-bot
"""
import os
import time
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv

from src.market_api import KalshiClient
from src.opportunity_analyzer import ArbitrageAnalyzer, ArbitrageOpportunity
from src.execution_engine import TradeExecutor, TradeOpportunity

load_dotenv()


class KalshiArbitrageBot:
    """
    Main trading bot orchestrator for identifying and executing arbitrage opportunities.
    
    This class coordinates market scanning, opportunity analysis, and trade execution
    across multiple market types. It intelligently filters markets by liquidity,
    calculates net profitability after fees, and provides comprehensive reporting
    on discovered opportunities.
    
    The bot identifies two primary opportunity types:
    - Probability Arbitrage: Market inefficiencies where contract probabilities
      deviate from expected 100% total, creating guaranteed profit scenarios.
    - Spread Trading: Orderbook imbalances where immediate buy-sell execution
      generates instant profit with minimal risk exposure.
    """
    
    def __init__(self, auto_execute_trades: bool = False):
        """
        Initialize the bot.
        
        Args:
            auto_execute_trades: If True, automatically execute profitable trades
        """
        self.client = KalshiClient()
        self.arbitrage_analyzer = ArbitrageAnalyzer()
        self.trade_executor = TradeExecutor(
            client=self.client,
            min_profit_cents=int(os.getenv("MIN_PROFIT_CENTS", "2")),
            max_position_size=int(os.getenv("MAX_POSITION_SIZE", "1000")),
            auto_execute=auto_execute_trades
        )
        
        self.min_profit_per_day = float(os.getenv("MIN_PROFIT_PER_DAY", "0.1"))
        self.min_liquidity = int(os.getenv("MIN_LIQUIDITY", "10000"))
    
    def filter_markets_by_liquidity(self, markets: List[Dict]) -> List[Dict]:
        """
        Filter markets to only include those with sufficient liquidity.
        
        Only includes markets that have:
        - Liquidity >= minimum threshold
        - Both bid and ask prices available (tradeable)
        
        Args:
            markets: List of market dictionaries from API
            
        Returns:
            Filtered list of markets with sufficient liquidity
        """
        return [
            market for market in markets
            if market.get("liquidity", 0) >= self.min_liquidity
            and self._has_tradeable_liquidity(market)
        ]
    
    def _has_tradeable_liquidity(self, market: Dict) -> bool:
        """Check if market has tradeable bid/ask prices."""
        yes_bid = market.get("yes_bid")
        yes_ask = market.get("yes_ask")
        no_bid = market.get("no_bid")
        no_ask = market.get("no_ask")
        
        has_yes_liquidity = yes_bid is not None and yes_ask is not None and yes_bid != yes_ask
        has_no_liquidity = no_bid is not None and no_ask is not None and no_bid != no_ask
        
        return has_yes_liquidity or has_no_liquidity
    
    def _fetch_and_filter_markets(self, limit: int) -> List[Dict]:
        """
        Fetch and filter markets - optimized shared method to avoid duplication.
        
        Args:
            limit: Maximum number of markets to fetch
            
        Returns:
            Filtered list of markets with sufficient liquidity
        """
        markets = self.client.get_markets(limit=limit, status="open")
        if not markets:
            return []
        
        original_count = len(markets)
        filtered_markets = self.filter_markets_by_liquidity(markets)
        
        if filtered_markets:
            print(f"Found {original_count} active markets. "
                  f"Filtered to {len(filtered_markets)} markets with liquidity >= ${self.min_liquidity/100:.2f}")
        
        return filtered_markets
    
    def scan_arbitrage_opportunities(self, limit: int = 100) -> List[ArbitrageOpportunity]:
        """
        Scan active markets for probability arbitrage opportunities.
        
        Probability arbitrage occurs when the combined YES and NO contract probabilities
        deviate from the expected 100% total, indicating market inefficiency.
        
        Example Scenario:
            - YES contracts trading at 52¢
            - NO contracts trading at 50¢
            - Total probability: 102% (2% arbitrage opportunity)
        
        The method filters opportunities by minimum profit thresholds and liquidity
        requirements to ensure only viable trades are identified.
        
        Args:
            limit: Maximum number of markets to analyze (default: 100)
            
        Returns:
            List of ArbitrageOpportunity objects, sorted by profit per day (descending)
        """
        print(f"[{datetime.now()}] Scanning {limit} markets for arbitrage opportunities...")
        
        markets = self._fetch_and_filter_markets(limit)
        if not markets:
            print("No markets found or API error.")
            return []
        
        opportunities = self.arbitrage_analyzer.find_opportunities(markets, client=self.client)
        
        min_profit = self.min_profit_per_day
        filtered = [opp for opp in opportunities if opp.profit_per_day >= min_profit]
        
        return filtered
    
    def scan_immediate_trades(self, limit: int = 100, auto_execute: bool = False) -> List[TradeOpportunity]:
        """
        Scan markets for immediate spread trading opportunities.
        
        Spread trading opportunities arise when orderbook bid prices exceed ask prices,
        enabling simultaneous buy and sell execution for instant profit realization.
        
        Example Scenario:
            - Best bid: 43¢ (someone wants to buy)
            - Best ask: 42¢ (someone wants to sell)
            - Profit: 1¢ per contract (minus trading fees)
        
        This method identifies such opportunities and optionally executes them
        automatically when enabled.
        
        Args:
            limit: Maximum number of markets to analyze (default: 100)
            auto_execute: Enable automatic trade execution for profitable opportunities
            
        Returns:
            List of TradeOpportunity objects, sorted by net profit (descending)
        """
        print(f"[{datetime.now()}] Scanning {limit} markets for immediate trade opportunities...")
        
        markets = self._fetch_and_filter_markets(limit)
        if not markets:
            print("No markets found or API error.")
            return []
        
        original_auto_execute = self.trade_executor.auto_execute
        self.trade_executor.auto_execute = auto_execute
        
        try:
            opportunities = self.trade_executor.scan_and_execute(markets, limit=limit)
            opportunities.sort(key=lambda x: x.net_profit, reverse=True)
            return opportunities
        finally:
            self.trade_executor.auto_execute = original_auto_execute
    
    def scan_all_opportunities(self, limit: int = 100, auto_execute: bool = False):
        """
        Comprehensive market scan for all available trading opportunities.
        
        Performs simultaneous analysis of both probability arbitrage and spread trading
        opportunities across active markets. This method optimizes API usage by fetching
        market data once and applying both analysis types to the same dataset.
        
        Args:
            limit: Maximum number of markets to analyze (default: 100)
            auto_execute: Enable automatic execution of profitable spread trades
            
        Returns:
            Tuple containing:
                - arbitrage_opportunities: List of probability arbitrage opportunities
                - trade_opportunities: List of spread trading opportunities
                - executed_count: Number of trades automatically executed
        """
        print(f"[{datetime.now()}] Scanning {limit} markets for all opportunities...")
        
        markets = self._fetch_and_filter_markets(limit)
        if not markets:
            print("No markets found or API error.")
            return [], [], 0
        
        min_profit = self.min_profit_per_day
        arbitrage_opps = self.arbitrage_analyzer.find_opportunities(markets, client=self.client)
        arbitrage_opps = [opp for opp in arbitrage_opps if opp.profit_per_day >= min_profit]
        
        original_auto_execute = self.trade_executor.auto_execute
        self.trade_executor.auto_execute = False
        
        try:
            trade_opps = self.trade_executor.scan_and_execute(markets, limit=limit)
            trade_opps.sort(key=lambda x: x.net_profit, reverse=True)
        finally:
            self.trade_executor.auto_execute = original_auto_execute
        
        executed_count = 0
        if auto_execute and trade_opps:
            profitable_trades = [opp for opp in trade_opps if opp.net_profit > 0]
            for trade_opp in profitable_trades:
                success, message = self.trade_executor.execute_trade(trade_opp)
                if success:
                    print(f"[AUTO-EXECUTE] {message}")
                    executed_count += 1
        
        return arbitrage_opps, trade_opps, executed_count
    
    def display_arbitrage_opportunity(self, opp: ArbitrageOpportunity, index: int = None):
        """
        Display comprehensive details of a probability arbitrage opportunity.
        
        Args:
            opp: The ArbitrageOpportunity to display
            index: Optional index number for listing purposes
        """
        prefix = f"[{index}] " if index is not None else ""
        print(f"\n{prefix}{'='*60}")
        print(f"Market: {opp.market_title}")
        print(f"Ticker: {opp.market_ticker}")
        print(f"Total Probability: {opp.total_probability:.2f}%")
        print(f"Deviation from 100%: {opp.deviation:.2f}%")
        print(f"Expiration: {opp.expiration_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Days to Expiration: {opp.days_to_expiration:.2f}")
        print(f"\nProfit Analysis:")
        print(f"  Gross Profit: ${opp.gross_profit:.2f}")
        print(f"  Net Profit (after fees): ${opp.net_profit:.2f}")
        print(f"  Profit per Day: ${opp.profit_per_day:.2f}")
        print(f"\nRecommended Trades:")
        for i, trade in enumerate(opp.trades, 1):
            print(f"  {i}. {trade['action'].upper()} {trade['quantity']} contracts "
                  f"of {trade['ticker']} at {trade['price']}¢ "
                  f"(side: {trade['side']})")
        print(f"{'='*60}\n")
    
    def display_trade_opportunity(self, opp: TradeOpportunity, index: int = None):
        """
        Display comprehensive details of a spread trading opportunity.
        
        Args:
            opp: The TradeOpportunity to display
            index: Optional index number for listing purposes
        """
        prefix = f"[{index}] " if index is not None else ""
        print(f"\n{prefix}{'='*60}")
        print(f"Market: {opp.market_title}")
        print(f"Ticker: {opp.market_ticker}")
        print(f"Side: {opp.side.upper()}")
        print(f"Buy Price: {opp.buy_price}¢")
        print(f"Sell Price: {opp.sell_price}¢")
        print(f"Spread: {opp.spread}¢")
        print(f"Quantity: {opp.quantity} contracts")
        print(f"\nProfit Analysis:")
        print(f"  Gross Profit: ${opp.gross_profit:.2f}")
        print(f"  Net Profit (after fees): ${opp.net_profit:.2f}")
        print(f"  Profit per Contract: ${opp.net_profit / opp.quantity:.4f}")
        print(f"{'='*60}\n")
    
    def run_scan(self, limit: int = 100, display_all: bool = False, auto_execute: bool = False):
        """
        Execute a single comprehensive market scan and display results.
        
        Performs a complete analysis of active markets, identifying both probability
        arbitrage and spread trading opportunities. Results are presented in a
        user-friendly format with detailed profit analysis and recommendations.
        
        Args:
            limit: Maximum number of markets to analyze (default: 100)
            display_all: Display all opportunities when True, otherwise show top 10
            auto_execute: Enable automatic execution of profitable spread trades
        """
        arbitrage_opps, trade_opps, executed_count = self.scan_all_opportunities(
            limit=limit, auto_execute=auto_execute
        )
        
        if not arbitrage_opps and not trade_opps:
            print("\nNo profitable opportunities found that meet the current criteria.")
            if executed_count > 0:
                print(f"Successfully executed {executed_count} trades automatically.")
            return
        
        if trade_opps:
            print(f"\n{'='*70}")
            print(f"SPREAD TRADING OPPORTUNITIES: Found {len(trade_opps)} profitable opportunities!")
            print(f"{'='*70}\n")
            
            display_count = len(trade_opps) if display_all else min(10, len(trade_opps))
            display_opps = trade_opps[:display_count]
            for i, opp in enumerate(display_opps, 1):
                self.display_trade_opportunity(opp, index=i)
            
            remaining = len(trade_opps) - display_count
            if remaining > 0:
                print(f"\n... and {remaining} more spread trading opportunities.")
        
        if arbitrage_opps:
            print(f"\n{'='*70}")
            print(f"PROBABILITY ARBITRAGE OPPORTUNITIES: Found {len(arbitrage_opps)} profitable opportunities!")
            print(f"{'='*70}\n")
            
            display_count = len(arbitrage_opps) if display_all else min(10, len(arbitrage_opps))
            display_opps = arbitrage_opps[:display_count]
            for i, opp in enumerate(display_opps, 1):
                self.display_arbitrage_opportunity(opp, index=i)
            
            remaining = len(arbitrage_opps) - display_count
            if remaining > 0:
                print(f"\n... and {remaining} more arbitrage opportunities.")
        
        if trade_opps and arbitrage_opps:
            print(f"\n{'='*70}")
            print("COMPARISON:")
            print(f"{'='*70}")
            best_trade = trade_opps[0]
            best_arb = arbitrage_opps[0]
            
            print(f"Spread Trading: ${best_trade.net_profit:.2f} profit (instant execution)")
            print(f"Probability Arbitrage: ${best_arb.profit_per_day:.2f}/day (over {best_arb.days_to_expiration:.1f} days)")
            
            arb_total_profit = best_arb.profit_per_day * best_arb.days_to_expiration
            if best_trade.net_profit > arb_total_profit:
                print(f"\n→ RECOMMENDATION: Spread trading opportunity offers higher immediate profit!")
            elif best_arb.profit_per_day > 0:
                print(f"\n→ RECOMMENDATION: Probability arbitrage may provide better long-term returns!")
        
        if executed_count > 0:
            print(f"\n[AUTO-EXECUTE] Executed {executed_count} trades automatically.")
    
    def run_continuous(self, scan_interval: int = 300, limit: int = 100, 
                      auto_execute: bool = False, max_scans: int = None):
        """
        Run continuous market monitoring mode.
        
        Operates in a continuous loop, periodically scanning markets for new opportunities.
        This mode is ideal for long-term monitoring and automated trading strategies.
        The bot will continue running until manually stopped or maximum scan count is reached.
        
        Args:
            scan_interval: Time between scans in seconds (default: 300 = 5 minutes)
            limit: Maximum number of markets to analyze per scan iteration
            auto_execute: Enable automatic execution of profitable spread trades
            max_scans: Maximum number of scan iterations (None for unlimited)
        """
        print(f"Starting continuous market monitoring (scan interval: {scan_interval} seconds)...")
        if auto_execute:
            print("⚠️  WARNING: Auto-execute mode enabled - trades will be executed automatically!")
        if max_scans:
            print(f"Maximum scan iterations: {max_scans}")
        print("Press Ctrl+C to stop monitoring.\n")
        
        scan_count = 0
        try:
            while True:
                scan_count += 1
                if max_scans and scan_count > max_scans:
                    print(f"\nReached maximum scan count ({max_scans}). Stopping.")
                    break
                
                arbitrage_opps, trade_opps, executed_count = self.scan_all_opportunities(
                    limit=limit, auto_execute=auto_execute
                )
                
                total_opps = len(arbitrage_opps) + len(trade_opps)
                
                if total_opps > 0:
                    print(f"\n✅ Found {total_opps} profitable opportunities!")
                    print(f"  • {len(trade_opps)} spread trading opportunities")
                    print(f"  • {len(arbitrage_opps)} probability arbitrage opportunities")
                else:
                    print(f"\nNo profitable opportunities found (scan #{scan_count})")
                
                print(f"\nWaiting {scan_interval} seconds until next scan...\n")
                time.sleep(scan_interval)
        except KeyboardInterrupt:
            print("\n\nScanning stopped by user.")


def show_interactive_menu():
    """
    Display interactive menu and handle user selections.
    
    Shows a menu with all available features and prompts user for input parameters
    as needed before executing the selected feature.
    """
    import sys
    import os
    
    try:
        import inquirer
        
        print("\n" + "="*70)
        print("  KALSHI ARBITRAGE TRADING BOT - Interactive Menu")
        print("="*70 + "\n")
        
        menu_options = [
            "📊 Single Scan (All Opportunities)",
            "📈 Scan Spread Trading Opportunities Only",
            "🎯 Scan Probability Arbitrage Opportunities Only",
            "🔄 Continuous Monitoring Mode",
            "⚙️  Configure Settings",
            "❌ Exit"
        ]
        
        questions = [
            inquirer.List(
                'action',
                message="Select an option (Use ↑↓ arrows, Enter to select)",
                choices=menu_options,
            )
        ]
        
        try:
            answers = inquirer.prompt(questions)
        except (KeyboardInterrupt, EOFError, Exception):
            show_simple_menu()
            return
        
        if not answers:
            print("\nOperation cancelled.")
            return
        
        action = answers['action']
    except (ImportError, Exception):
        show_simple_menu()
        return
    
    bot = KalshiArbitrageBot(auto_execute_trades=False)
    
    if action == "📊 Single Scan (All Opportunities)":
        handle_single_scan(bot)
    elif action == "📈 Scan Spread Trading Opportunities Only":
        handle_trades_only_scan(bot)
    elif action == "🎯 Scan Probability Arbitrage Opportunities Only":
        handle_arbitrage_only_scan(bot)
    elif action == "🔄 Continuous Monitoring Mode":
        handle_continuous_monitoring(bot)
    elif action == "⚙️  Configure Settings":
        handle_configure_settings(bot)
    elif action == "❌ Exit":
        print("\nGoodbye! 👋")
        return


def show_simple_menu():
    """Fallback simple menu if terminal menu library is not available."""
    print("\n" + "="*70)
    print("  KALSHI ARBITRAGE TRADING BOT - Menu")
    print("="*70 + "\n")
    
    menu_options = [
        "Single Scan (All Opportunities)",
        "Scan Spread Trading Opportunities Only",
        "Scan Probability Arbitrage Opportunities Only",
        "Continuous Monitoring Mode",
        "Configure Settings",
        "Exit"
    ]
    
    print("Available options:")
    for i, option in enumerate(menu_options, 1):
        print(f"  {i}. {option}")
    
    try:
        choice = input("\nEnter your choice (1-6): ").strip()
        choice_num = int(choice)
        
        if 1 <= choice_num <= 6:
            bot = KalshiArbitrageBot(auto_execute_trades=False)
            
            if choice_num == 1:
                handle_single_scan(bot)
            elif choice_num == 2:
                handle_trades_only_scan(bot)
            elif choice_num == 3:
                handle_arbitrage_only_scan(bot)
            elif choice_num == 4:
                handle_continuous_monitoring(bot)
            elif choice_num == 5:
                handle_configure_settings(bot)
            elif choice_num == 6:
                print("\nGoodbye! 👋")
        else:
            print("Invalid choice. Please select 1-6.")
    except (ValueError, KeyboardInterrupt):
        print("\nOperation cancelled.")


def get_user_input(prompt, default="", validator=None):
    """Get user input with validation."""
    while True:
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            if not user_input:
                user_input = default
        else:
            user_input = input(f"{prompt}: ").strip()
        
        if validator:
            try:
                if validator(user_input):
                    return user_input
                else:
                    print("Invalid input. Please try again.")
            except Exception as e:
                print(f"Error: {e}")
        else:
            return user_input


def _get_yes_no_input(prompt: str, default: str = "n") -> bool:
    """Helper to get yes/no input and convert to boolean."""
    response = get_user_input(prompt, default,
                             lambda x: x.lower() in ['y', 'n', 'yes', 'no'])
    return response.lower() in ['y', 'yes']


def handle_single_scan(bot):
    """Handle single scan with all opportunities."""
    print("\n" + "="*70)
    print("  Single Scan Configuration")
    print("="*70 + "\n")
    
    limit = int(get_user_input("Number of markets to scan", "100", 
                                lambda x: x.isdigit() and int(x) > 0))
    
    display_all = _get_yes_no_input("Display all opportunities? (y/n)", "n")
    auto_execute = _get_yes_no_input("⚠️  Enable automatic trade execution? (y/n) - USE WITH CAUTION", "n")
    
    if auto_execute and not bot.trade_executor.auto_execute:
        bot = KalshiArbitrageBot(auto_execute_trades=True)
    
    print(f"\n{'='*70}")
    print(f"Starting scan of {limit} markets...")
    print(f"{'='*70}\n")
    
    bot.run_scan(limit=limit, display_all=display_all, auto_execute=auto_execute)


def handle_trades_only_scan(bot):
    """Handle spread trading opportunities scan."""
    print("\n" + "="*70)
    print("  Spread Trading Scan Configuration")
    print("="*70 + "\n")
    
    limit = int(get_user_input("Number of markets to scan", "100",
                                lambda x: x.isdigit() and int(x) > 0))
    
    display_all = _get_yes_no_input("Display all opportunities? (y/n)", "n")
    auto_execute = _get_yes_no_input("⚠️  Enable automatic trade execution? (y/n) - USE WITH CAUTION", "n")
    
    if auto_execute and not bot.trade_executor.auto_execute:
        bot = KalshiArbitrageBot(auto_execute_trades=True)
    
    print(f"\n{'='*70}")
    print(f"Scanning {limit} markets for spread trading opportunities...")
    print(f"{'='*70}\n")
    
    opportunities = bot.scan_immediate_trades(limit=limit, auto_execute=auto_execute)
    if opportunities:
        display_count = len(opportunities) if display_all else min(10, len(opportunities))
        for i, opp in enumerate(opportunities[:display_count], 1):
            bot.display_trade_opportunity(opp, index=i)
        if len(opportunities) > display_count:
            print(f"\n... and {len(opportunities) - display_count} more opportunities.")
    else:
        print("\nNo spread trading opportunities found.")


def handle_arbitrage_only_scan(bot):
    """Handle probability arbitrage opportunities scan."""
    print("\n" + "="*70)
    print("  Probability Arbitrage Scan Configuration")
    print("="*70 + "\n")
    
    limit = int(get_user_input("Number of markets to scan", "100",
                                lambda x: x.isdigit() and int(x) > 0))
    
    display_all = _get_yes_no_input("Display all opportunities? (y/n)", "n")
    
    print(f"\n{'='*70}")
    print(f"Scanning {limit} markets for probability arbitrage opportunities...")
    print(f"{'='*70}\n")
    
    opportunities = bot.scan_arbitrage_opportunities(limit=limit)
    if opportunities:
        display_count = len(opportunities) if display_all else min(10, len(opportunities))
        for i, opp in enumerate(opportunities[:display_count], 1):
            bot.display_arbitrage_opportunity(opp, index=i)
        if len(opportunities) > display_count:
            print(f"\n... and {len(opportunities) - display_count} more opportunities.")
    else:
        print("\nNo probability arbitrage opportunities found.")


def handle_continuous_monitoring(bot):
    """Handle continuous monitoring mode."""
    print("\n" + "="*70)
    print("  Continuous Monitoring Configuration")
    print("="*70 + "\n")
    
    interval = int(get_user_input("Scan interval in seconds", "300",
                                  lambda x: x.isdigit() and int(x) > 0))
    
    limit = int(get_user_input("Number of markets to scan per iteration", "100",
                               lambda x: x.isdigit() and int(x) > 0))
    
    auto_execute = _get_yes_no_input("⚠️  Enable automatic trade execution? (y/n) - USE WITH CAUTION", "n")
    
    max_scans_input = get_user_input("Maximum number of scans (press Enter for unlimited)", "",
                                     lambda x: x == "" or (x.isdigit() and int(x) > 0))
    max_scans = int(max_scans_input) if max_scans_input else None
    
    if auto_execute and not bot.trade_executor.auto_execute:
        bot = KalshiArbitrageBot(auto_execute_trades=True)
    
    bot.run_continuous(
        scan_interval=interval,
        limit=limit,
        auto_execute=auto_execute,
        max_scans=max_scans
    )


def handle_configure_settings(bot):
    """Handle settings configuration."""
    print("\n" + "="*70)
    print("  Bot Settings Configuration")
    print("="*70 + "\n")
    
    current_min_liquidity = bot.min_liquidity / 100  # Convert cents to dollars
    
    min_liquidity_input = get_user_input(
        f"Minimum liquidity in dollars (current: ${current_min_liquidity:.2f})",
        str(current_min_liquidity),
        lambda x: x.replace('.', '').replace('-', '').isdigit() and float(x) > 0
    )
    
    min_liquidity_dollars = float(min_liquidity_input)
    bot.min_liquidity = int(min_liquidity_dollars * 100)  # Convert to cents
    
    print(f"\n✅ Settings updated:")
    print(f"   Minimum liquidity: ${min_liquidity_dollars:.2f}")
    print("\nPress Enter to return to main menu...")
    input()
    show_interactive_menu()


def main():
    """
    Main entry point for the Kalshi Arbitrage Trading Bot.
    
    Launches the interactive menu system for user-friendly operation.
    """
    show_interactive_menu()


if __name__ == "__main__":
    main()

