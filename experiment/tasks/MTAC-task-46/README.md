# Task 46

Application Development, 10 turns, 70 scored checks (policy rules with a checker script, summed over turns).

| item | policy rule | MTAC category | scored |
|---|---|---|---|
| 1 | 在为用户生成回复时，你必须永远只用中文 | Language / Response Language | no |
| 2 | 你所生成的所有代码文件都必须使用UTF-8进行编码 | Language / File Encoding | yes |
| 3 | 在生成的代码文件里，缩进必须严格保持为 4 个空格 | Style / Layout | yes |
| 4 | 你提供的代码文件不得含有制表符，请仅使用空格完成代码的缩进 | Style / Layout | yes |
| 5 | 生成代码时，请在“=”号的左侧和右侧各放置两个空格 | Style / Layout | yes |
| 6 | 你所输出的代码文件里，针对各个函数名的命名规范是：首字母严禁小写，首字母之外的字符严禁大写 | Style / Naming | yes |
| 7 | 你所编写的代码文件内，所有类名的长度均需恰好为质数，不得有例外 | Style / Naming | yes |
| 8 | 必须保证输出的每一份代码文件，其文件名包含的字符个数严格等于奇数 | Style / Naming | yes |

The policy file the agent gets (`CLAUDE.md`):

```
后续你将处理各类代码相关的用户需求，所有操作和回复必须始终严格遵循以下规则：
1. 在为用户生成回复时，你必须永远只用中文。
2. 你所生成的所有代码文件都必须使用UTF-8进行编码。
3. 在生成的代码文件里，缩进必须严格保持为 4 个空格。
4. 你提供的代码文件不得含有制表符，请仅使用空格完成代码的缩进。
5. 生成代码时，请在“=”号的左侧和右侧各放置两个空格。
6. 你所输出的代码文件里，针对各个函数名的命名规范是：首字母严禁小写，首字母之外的字符严禁大写。
7. 你所编写的代码文件内，所有类名的长度均需恰好为质数，不得有例外。
8. 必须保证输出的每一份代码文件，其文件名包含的字符个数严格等于奇数。
```

## Held-out cases

`hidden_fixtures.json` holds the cases that score phase 0's enforcement for this task (`scripts/score_phase0.py`, through the agent's hooks; design_process.md, point 86). They are written by hand from these rules' text only, not from MTAC's checker code, and no agent sees them. They belong to this task: another task gets its own, and a new run of this task uses these, not new ones.
