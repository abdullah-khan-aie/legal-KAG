import logging

from kag.common.utils import get_now
from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_expression_builder")
class ExpressionBuildr(PromptABC):
    template_en = (
        f"Today is {get_now(language='en')}。\n"
        + """# instruction
Generate Python code based on the given question and context data to output the result. 
Show extracted data from context, intermediate calculations and final results for clarity.
Strictly use input content without making assumptions (e.g., if disability grade isn't mentioned, assume no disability).
Return "I don't know." if question cannot be answered.

# output format
Output only Python 3.8 code without any additional information

# examples
## Example 1
### input
#### question
Calculate interest for 47,000元 at 0.015% daily rate over 612 days
### output
```python
# Initial principal
principal = 47000

# Daily rate (0.015‰)
rate = 1.5 / 10000

# Days
days = 612

# Calculate annual rate
annual_rate = rate * 365

# Calculate interest
interest = principal * (annual_rate / 365) * days

# Calculate total
total = principal + interest

print(f"Total amount: {total:.2f} yuan")
```
## Example 2
### input
#### question
Calculate 2019 game revenue growth rate and predict 2020 revenue based on 2018-2019 data
#### context
2018 game revenue: 13M, 2019 game revenue: 15.8M
### output
```python
# 2018-2019 revenue (million)
revenue_2018 = 1300
revenue_2019 = 1580

# Calculate growth rate
growth_rate = (revenue_2019 - revenue_2018) / revenue_2018
print(f"Growth rate: {growth_rate*100:.2f}%")

# Predict 2020 revenue
revenue_2020 = revenue_2019 * (1 + growth_rate)
print(f"2020 projected revenue: {revenue_2020:.2f} million")
```

# input
## question
$question
## context
$context
## error
$error
    """
    )

    @property
    def template_variables(self) -> list[str]:
        return ["question", "context", "error"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = rsp.strip().strip("```").strip("python")
        return rsp
