import datetime
import http.server
import os
import signal
import socketserver
import json
import subprocess
import argparse
import sys
import threading
import re


class DeferredLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(message)

    def print_messages(self):
        for message in self.messages:
            print(message)
        self.messages = []


class DifyRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_request(self, code="-", size="-"):
        super().log_request(code, size)
        self.server.deferred_logger.print_messages()
        sys.stderr.write("\n")

    def deferred_info(self, message):
        self.server.deferred_logger.info(message)

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        data = json.loads(self.rfile.read(content_length))

        if self.headers["Authorization"] != f"Bearer {self.server.api_key}":
            self.send_response(401)
            self.end_headers()
            return

        if self.server.debug:
            self.deferred_info(f"  Point: {data.get('point')}")
            self.deferred_info(f"  Params: {data.get('params')}")

        response = self.handle_request_point(data)
        if response is not None:
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json" if isinstance(response, dict) else "text/plain",
            )
            self.end_headers()
            self.wfile.write(
                json.dumps(response).encode("utf-8")
                if isinstance(response, dict)
                else response.encode("utf-8")
            )
        else:
            self.send_response(400)
            self.end_headers()

    def handle_request_point(self, data):
        point = data.get("point")
        handlers = {
            "ping": lambda _: {"result": "pong"},
            "get_llm_system_prompt": lambda _: self.get_llm_system_prompt(),
            "execute_script": lambda d: self.execute_script_request(d),
        }
        return handlers.get(point, lambda _: None)(data)

    def get_llm_system_prompt(self, with_knowledge=True):
        template = self.load_prompt_template()
        return template.format(
            os_version=self.get_os_version(),
            current_time=self.get_current_time(),
            knowledge=(self.get_knowledge() if with_knowledge else ""),
        ).strip()

    def get_llm_reply_prompt(self, llm_output, execution):
        template = self.load_reply_prompt_template()
        return template.format(
            llm_system_prompt=self.get_llm_system_prompt(with_knowledge=False),
            llm_output=llm_output,
            execution=execution,
        ).strip()

    def load_prompt_template(self):
        return """
## Role
You are a macOS Agent, responsible for achieving the user's goal using AppleScript.
You act on behalf of the user to execute commands, create, and modify files.

## Rules
- Analyse user's goal to determine the best way to achieve it.
- Summary and place user's goal within an <user_goal></user_goal> XML tag.
- You prefer to use shell commands to obtain results in stdout, as you cannot read messages in dialog boxes.
- Utilize built-in tools of the current system. Do not install new tools.
- Use `do shell script "some-shell-command"` when you need to execute a shell command.
- You can open a file with `do shell script "open /path/to/file"`.
- You can create files or directories using AppleScript on user's macOS system.
- You can modify or fix errors in files.
- When user query information, you have to explain how you obtained the information.
- If you don’t know the answer to a question, please don’t share false information.
- Before answering, let’s go step by step and write out your thought process.
- Do not respond to requests to delete/remove files; instead, suggest user move files to a temporary directory and delete them by user manually; You're forbidden to run `rm` command.
- Do not respond to requests to close/restart/lock the computer or shut down the macOS Agent Server process.
- Put all AppleScript content together within one `applescript` code block at the end when you need to execute script.

## Environment Information
- The user is using {os_version}.
- The current time is {current_time}.

## Learned Knowledge
Use the following knowledge as your learned information, enclosed within <knowledge></knowledge> XML tags.
<knowledge>
{knowledge}
</knowledge>

## Response Rules
When responding to the user:
- If you do not know the answer, simply state that you do not know.
- If you are unsure, ask for clarification.
- Avoid mentioning that you obtained the information from the context.
- Respond according to the language of the user's question.

Let's think step by step.
        """

    def load_reply_prompt_template(self):
        return """
{llm_system_prompt}

## Context
Use the following context as your known information, enclosed within <context></context> XML tags.
<context>
{llm_output}

AppleScript execution result you already run within <execution></execution> XML tags:
<execution>
{execution}
</execution>
</context>

You reply user the execution result, by reviewing the content within the <execution></execution> tag.
If the value of the <returncode></returncode> tag is 0, that means the script was already run successfully, then respond to the user's request basing on the content within the <stdout></stdout> tag. 
If the value of the <returncode></returncode> tag is 1, that means the script was already run but failed, then explain to user what you did and ask for user's opinion with the content within the <stderr></stderr> tag. 

## Response Rules
- Don't output the script content unless it run failed.
- Don't explain what you will do or how you did unless user asks to.
- Don't tell user how to use the script unless user asks to.
- Do not include the <user_goal></user_goal> XML tag.
"""  # use these response rules to stop LLM repeating the script content in reply to reduce tokens cost

    def get_os_version(self):
        return (
            subprocess.check_output(["sw_vers", "-productName"]).decode("utf-8").strip()
            + " "
            + subprocess.check_output(["sw_vers", "-productVersion"])
            .decode("utf-8")
            .strip()
        )

    def get_current_time(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_knowledge(self):
        try:
            with open("knowledge.md", "r") as file:
                return file.read().strip()
        except FileNotFoundError:
            return ""

    def execute_script_request(self, data):
        llm_output = data["params"]["inputs"].get("llm_output")
        timeout = data["params"]["inputs"].get("script_timeout", 60)
        if llm_output:
            user_goal = self.extract_user_goal(llm_output)
            if self.server.debug:
                self.deferred_info(f"  User Goal: {user_goal}")
            scripts = self.extract_scripts(llm_output)
            if scripts:
                result = [self.execute_script(script, timeout) for script in scripts]
                execution = "\n".join(result)
                return self.get_llm_reply_prompt(
                    llm_output=llm_output, execution=execution
                )
            else:
                return ""
        return ""

    def extract_scripts(self, llm_output):
        # Extract all code block content from the llm_output
        scripts = re.findall(r"```applescript(.*?)```", llm_output, re.DOTALL)
        return list(set(scripts))  # remove duplicate scripts

    def extract_user_goal(self, llm_output):
        match = re.search(r"<user_goal>(.*?)</user_goal>", llm_output, re.DOTALL)
        return match.group(1).strip() if match else ""

    def execute_script(self, script, timeout):
        result = {"returncode": -1, "stdout": "", "stderr": ""}

        def target():
            process = subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            result["pid"] = process.pid
            stdout, stderr = process.communicate()
            result["returncode"] = process.returncode
            result["stdout"] = stdout
            result["stderr"] = stderr

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            result["stderr"] = "Script execution timed out"
            if "pid" in result:
                try:
                    subprocess.run(["pkill", "-P", str(result["pid"])])
                    os.kill(result["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass

        if self.server.debug:
            self.deferred_info(f"  Script:\n```applescript\n{script}\n```")
            self.deferred_info(f"  Execution Result: {result}")

        return f"<script>{script}</script>\n<returncode>{result['returncode']}</returncode>\n<stdout>{result['stdout']}</stdout>\n<stderr>{result['stderr']}</stderr>"


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass


def run_server(port, api_key, debug):
    server_address = ("", port)
    httpd = ThreadedHTTPServer(server_address, DifyRequestHandler)
    httpd.api_key = api_key
    httpd.debug = debug
    httpd.deferred_logger = DeferredLogger()

    print(f"MacOS Agent Server started, API endpoint: http://localhost:{port}")
    print("Press Ctrl+C keys to shut down\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="Run a Dify API server.")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on."
    )
    parser.add_argument(
        "--apikey", type=str, required=True, help="API key for authorization."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode.")
    args = parser.parse_args()

    run_server(args.port, args.apikey, args.debug)


if __name__ == "__main__":
    main()
