# Task 51

Application Development, 9 turns, 54 scored checks (policy rules with a checker script, summed over turns).

| item | policy rule | MTAC category | scored |
|---|---|---|---|
| 1 | 任何回复的起始处都必须包含语气词"汪～"不可遗漏 | Content / Persona | yes |
| 2 | 所有回复都必须在结尾处加上"呜～"语气词 | Content / Persona | yes |
| 3 | 对于生成的每一个代码文件，都请不要在其中书写注释 | Quantity / Exact Value | yes |
| 4 | 生成的代码文件内不允许出现多层if | Quantity / Complexity | no |
| 5 | 写代码时请杜绝过度设计，用最短路径去实现即可，千万别自作主张加入兜底或降级方案等需求外的东西 | Style / Paradigm | no |
| 6 | 你生成的代码文件中不得出现while循环 | Style / Paradigm | yes |
| 7 | 生成的代码项目最多只能包含2个目录层级 | Quantity / Complexity | yes |
| 8 | 算上所有的空行，每个生成的代码文件的总行数必须保持为奇数 | Quantity / Exact Value | yes |

The policy file the agent gets (`CLAUDE.md`):

```
你作为具备代码生成、文件操作权限的代码智能体，后续所有交互轮次都必须严格遵循以下要求：
1. 任何回复的起始处都必须包含语气词"汪～"不可遗漏。
2. 所有回复都必须在结尾处加上"呜～"语气词。
3. 对于生成的每一个代码文件，都请不要在其中书写注释。
4. 生成的代码文件内不允许出现多层if。
5. 写代码时请杜绝过度设计，用最短路径去实现即可，千万别自作主张加入兜底或降级方案等需求外的东西。
6. 你生成的代码文件中不得出现while循环。
7. 生成的代码项目最多只能包含2个目录层级。
8. 算上所有的空行，每个生成的代码文件的总行数必须保持为奇数。
```
