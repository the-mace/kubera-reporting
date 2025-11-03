"""AI prompt templates for portfolio analysis."""

# Prompt template when dollar amounts should be hidden (percentages only)
AI_SUMMARY_PROMPT_NO_AMOUNTS = """Analyze this {period} portfolio report (currency: {currency}).

Format your response as:
1. First sentence: Overall net worth change summary (percentage only)
2. Blank line
3. "Key drivers:" followed by bullet points for top_dollar_movers (biggest impact on net worth)
4. If any top_percent_movers are NOT in top_dollar_movers AND have notable % changes (>5%):
   - Blank line
   - "Also notable:" followed by bullet points for those percentage movers

Note: "is_holding": true means individual stock/crypto/asset within a larger account.

CRITICAL RULES:
- Do NOT mention specific amounts - use only percentages
- Format bullets with "• " character
- Do NOT suggest actions or what to watch
- Do NOT mention asset allocation (shown in pie chart)
- ONLY use data provided - do not infer
- Keep factual and concise
- Only include "Also notable:" section if there are items to show

Portfolio Data:
{portfolio_data}"""

# Prompt template when dollar amounts should be shown
AI_SUMMARY_PROMPT_WITH_AMOUNTS = """Analyze this {period} portfolio report (currency: {currency}).

Format your response as:
1. First sentence: Overall net worth change summary
2. Blank line
3. "Key drivers:" followed by bullet points for top_dollar_movers (biggest impact on net worth)
4. If any top_percent_movers are NOT in top_dollar_movers AND have notable % changes (>5%):
   - Blank line
   - "Also notable:" followed by bullet points for those percentage movers

Note: "is_holding": true means individual stock/crypto/asset within a larger account.

CRITICAL RULES:
- Use exact names from the data
- Use {currency_symbol} symbol for amounts (this portfolio uses {currency})
- Format amounts WITHOUT decimals (e.g., {currency_symbol}1,234 not {currency_symbol}1,234.56)
- Format percentages with 2 decimal places (e.g., 5.13%)
- Format bullets with "• " character
- Do NOT suggest actions or what to watch
- Do NOT mention asset allocation (shown in pie chart)
- ONLY use data provided - do not infer
- Keep factual and concise
- Only include "Also notable:" section if there are items to show

Portfolio Data:
{portfolio_data}"""
