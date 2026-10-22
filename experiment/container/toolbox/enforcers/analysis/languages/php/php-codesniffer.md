# Analysis › Languages › PHP › PHP_CodeSniffer
enforcer · Checks PHP code against a coding standard (PSR-12 and others); `phpcbf` fixes what it can.

- no recipe: PHP and phpcs
- check: `php <phpcs.phar> --standard=<standard> <file>`

From the leaf's note:

Install: `apt-get update && apt-get install -y php-cli php-xml` (PHP 8.2), then
`wget -q https://github.com/PHPCSStandards/PHP_CodeSniffer/releases/download/4.0.4/phpcs.phar -O /opt/enforce/phpcs.phar`.
Use: `php /opt/enforce/phpcs.phar --standard=/opt/enforce/ruleset.xml --report=json <file>`.

Docs: https://github.com/PHPCSStandards/PHP_CodeSniffer/wiki
