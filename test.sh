#!/bin/bash
# set -x

# Function to print in green
print_green() {
	printf "\e[32m%s\e[0m\n" "$1"
}

# Function to print in red
print_red() {
	printf "\e[31m%s\e[0m\n" "$1"
}

# Parse command-line options
while [[ $# -gt 0 ]]; do
	case "$1" in
		--api)
			api_url="$2"
			shift 2
			;;
		--apikey)
			api_key="$2"
			shift 2
			;;
		*)
			echo "Unknown option: $1"
			exit 1
			;;
	esac
done

# Check if both API URL and API key are provided
if [ -z "$api_url" ] || [ -z "$api_key" ]; then
	echo "Both API URL and API key are required. Use --api http://localhost:8088 --apikey a-secret-key"
	exit 1
fi

# Test case 1
echo "point=ping"
response=$(curl -s -X POST $api_url -H "Content-Type: application/json" -H "Authorization: Bearer $api_key" -d '{"point": "ping"}')
expected='{"result": "pong"}'
if [ "$response" == "$expected" ]; then
	print_green "Test passed: $response"
else
	print_red "Test failed: expected '$expected', got '$response'"
fi

# Test case 2
echo "point=get_llm_system_prompt"
response=$(curl -s -X POST $api_url -H "Content-Type: application/json" -H "Authorization: Bearer $api_key" -d '{"point": "get_llm_system_prompt"}')
expected='## Environment Information'
if [[ "$response" == *"$expected"* ]]; then
	print_green "Test passed: $response"
else
	print_red "Test failed: expected to contain '$expected', got '$response'"
fi

# Test case 3
echo "point=execute_script, llm_output is having code block"
response=$(curl -s -X POST $api_url -H "Content-Type: application/json" -H "Authorization: Bearer $api_key" -d '{"point": "execute_script", "params": {"inputs": {"llm_output": "```applescript\ntell application \"System Settings\" to activate```"}}}' | tr -d '\n')
expected="<script>tell application \"System Settings\" to activate</script><returncode>0</returncode><stdout></stdout><stderr></stderr>"
if [[ "$response" == *"$expected"* ]]; then
	print_green "Test passed: $response"
else
	print_red "Test failed: expected '$expected', got '$response'"
fi

# Test case 4
echo "point=execute_script, llm_output is not having code block"
response=$(curl -s -X POST $api_url -H "Content-Type: application/json" -H "Authorization: Bearer $api_key" -d '{"point": "execute_script", "params": {"inputs": {"llm_output": "open system settings"}}}' | tr -d '\n')
expected=""
if [ "$response" == "$expected" ]; then
	print_green "Test passed: $response"
else
	print_red "Test failed: expected '$expected', got '$response'"
fi

# Test case 5
echo "point=execute_script, llm_output is empty"
response=$(curl -s -X POST $api_url -H "Content-Type: application/json" -H "Authorization: Bearer $api_key" -d '{"point": "execute_script", "params": {"inputs": {"llm_output": ""}}}' | tr -d '\n')
expected=""
if [ "$response" == "$expected" ]; then
	print_green "Test passed: $response"
else
	print_red "Test failed: expected '$expected', got '$response'"
fi

# Test case 6
echo "point=execute_script, run top command with timeout limit"
response=$(curl -s -X POST $api_url -H "Content-Type: application/json" -H "Authorization: Bearer $api_key" -d '{"point": "execute_script", "params": {"inputs": {"llm_output": "```applescript\ndo shell script \"top\"```", "script_timeout": 3}}}' | tr -d '\n')
expected="Script execution timed out"
if [[ "$response" == *"$expected"* ]]; then
	print_green "Test passed: $response"
else
	print_red "Test failed: expected to contain '$expected', got '$response'"
fi

# Test case 7: llm_output having <user_goal>a user goal</user_goal>
echo "point=execute_script, llm_output having <user_goal>a user goal</user_goal>"
response=$(curl -s -X POST $api_url -H "Content-Type: application/json" -H "Authorization: Bearer $api_key" -d '{"point": "execute_script", "params": {"inputs": {"llm_output": "<user_goal>a user goal</user_goal>"}}}' | tr -d '\n')
expected="" # it should be print in server log with --debug flag
if [[ "$response" == *"$expected"* ]]; then
	print_green "Test passed: $response"
else
	print_red "Test failed: expected to contain '$expected', got '$response'"
fi
