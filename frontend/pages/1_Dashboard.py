import streamlit as st
import json

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# from src.backtesting.backtesting_engine import BacktestingEngine
# from src.core.strategies.strategy_factory import StrategyFactory

st.header("Welcome to My Systematic Fund Backtesing Dashboard")
st.write("This page displays strategy params and backtesting results")

# Example list of strategies
strategies = { "Fixed Weight Portfolio": "fwp_strategy", "Markowitz Portfolio": "mv_strategy" }

# Multiselect for user to pick strategies
selected_strategies = st.multiselect("Select strategies:", list(strategies.keys()))

if st.button("Run Backtests"):
    for display_name in selected_strategies:
        strategy_type = strategies[display_name]
        
        with open(f"src/config/{strategy_type}.json", 'r') as f:
            stored_json = json.load(f)

        # Show stored JSON in text area for editing
        json_str = json.dumps(stored_json, indent=2)
        user_input = st.text_area("Edit JSON config:", value=json_str, height=300)

        # Use user-supplied JSON if valid, else fallback to stored
        try:
            config = json.loads(user_input)
            st.success("Using user-supplied JSON.")
        except json.JSONDecodeError:
            config = stored_json
            st.warning("Invalid JSON, using stored config.")

        st.json(config)

# strategy = StrategyFactory()