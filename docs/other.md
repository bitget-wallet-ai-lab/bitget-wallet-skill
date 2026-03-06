# Other

### Common Pitfalls

1. **Wrong chain code**: Use `sol` not `solana`, `bnb` not `bsc`. See the Chain Identifiers table below.
2. **Batch endpoints format**: `batch-token-info` uses `--tokens "sol:<addr1>,eth:<addr2>"` — chain and address are colon-separated, pairs are comma-separated.
3. **Liquidity pools**: The `liquidity` command returns pool info including LP lock percentage. 100% locked LP is generally a positive signal; 0% means the creator can pull liquidity.
4. **Stale quotes**: If more than ~30 seconds pass between getting a quote and executing, prices may have moved. Re-quote for time-sensitive trades.
5. **Insufficient gas**: A swap can fail silently if the wallet lacks native tokens for gas. The transaction still consumes gas fees even when it reverts. Check balance before proceeding.
6. **Missing token approval (EVM)**: On EVM chains, forgetting to approve the token for the router is the #1 cause of failed swaps. The transaction will revert on-chain and waste gas. See "EVM Token Approval" section above.
7. **Automate the boring parts**: Run security/liquidity/quote checks silently. Only surface results to the user in the final confirmation summary unless something is wrong.

