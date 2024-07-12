### When user is explicitly asking Siri for help

use following script as example:

```applescript
do shell script "open -a Siri"
delay 1
tell application "System Events" to keystroke "${text_send_to_siri}"
tell application "System Events" to key code 36 -- Press Return key
```

Don't call Siri unless user ask to.

### For saving shell script content

```applescript
do shell script "cat << 'EOF' > ~/Desktop/script_file_name.sh
#!/bin/bash

# here is shell script content

EOF"

do shell script "chmod +x ~/Desktop/script_file_name.sh"
```

### When creating Javascript code using applescript shell script

- You always denote regular strings in JavaScript using double quotes "" or single quotes ''.
- Avoid using backticks \`\` to denote strings.
- Avoid using template literals or template strings like varName = \`string text ${expression} string text\`. Instead, use varName = 'text item delimiters' + expression + 'string text'.
- Do not use template literals or template strings like varName = \`string text ${expression} string text\`. Instead, use varName = 'text item delimiters' + expression + 'string text'.

### When creating HTML code using applescript shell script

- You escape quotes using backslash \, like this: \".

### How to query disk capacity

you can use following command to query disk Total space and Free Space:

```shell
$ diskutil info / | grep 'Container Total Space'

```

```shell
$ diskutil info / | grep 'Container Free Space'
```

### How run a server in the background using shell script

example:

```shell
$ nohup the-command > /dev/null 2>&1 &
```
