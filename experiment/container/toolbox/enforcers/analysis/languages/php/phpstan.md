# Analysis › Languages › PHP › PHPStan
enforcer · Static analysis for PHP: types, unknown methods, dead code; strictness from level 0 to 10, and custom rules.

- no recipe: PHP and phpstan.phar
- check: `php <phpstan.phar> analyse --no-progress --level=<n> <file>`

From the leaf's note:

Install: PHP (as in the PHP_CodeSniffer note), then `wget -q https://github.com/phpstan/phpstan/releases/download/2.3.1/phpstan.phar -O /opt/enforce/phpstan.phar`.
Use: `php /opt/enforce/phpstan.phar analyse --no-progress --error-format=json -c /opt/enforce/phpstan.neon <file>`.

Docs: https://phpstan.org/
