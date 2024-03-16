## Awesome optimizer project
Credit to 
https://github.com/morten-nl/holdetdk-scraper
for providing endpoint examples for Holdet API.

# Usage
- Get API key from https://www.api-football.com/

Example code snippet to get optimal team given odds and fixtures in the current Holdet round.
```
odds_data = ApiFootball("paste_api_key_here")
holdet_data = HoldetDk()
optimization_input = OptimizationInput(holdet_data, odds_data, team_id_map=TEAM_ID_MAP, events=EVENTS)
optimization = Optimization(optimization_input)
optimization.build_model()
optimization.run()
r = optimization.get_result()
```