# Tests › Runners › PHPUnit
enforcer · The PHP test framework.

- no recipe: PHP and phpunit.phar
- check: `php <phpunit.phar>` in the project

From the leaf's note:

Install: PHP (`apt-get update && apt-get install -y php-cli php-xml php-mbstring`, PHP 8.2), then
`wget -q https://phar.phpunit.de/phpunit-11.5.57.phar -O /opt/enforce/phpunit.phar` (PHPUnit 11 runs on PHP 8.2).
Use: `php /opt/enforce/phpunit.phar <test folder>`.

Docs: https://docs.phpunit.de/
