import os
import discord
from discord.ext import commands
import io
import textwrap
import traceback
import pathlib
import asyncio
import re
from contextlib import redirect_stdout

class Eval(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot._last_result = None
        # Patterns to filter out sensitive information
        self.sensitive_patterns = [
            r'["\']token["\']\s*[:=]\s*["\'][^"\']*["\']',
            r'["\']bot_token["\']\s*[:=]\s*["\'][^"\']*["\']',
            r'["\']discord_token["\']\s*[:=]\s*["\'][^"\']*["\']',
            r'["\']password["\']\s*[:=]\s*["\'][^"\']*["\']',
            r'["\']secret["\']\s*[:=]\s*["\'][^"\']*["\']',
            r'["\']api_key["\']\s*[:=]\s*["\'][^"\']*["\']',
            r'[A-Za-z0-9]{24}\.[A-Za-z0-9]{6}\.[A-Za-z0-9_\-]{27}',
            r'[A-Za-z0-9]{32}',
        ]

    def _filter_sensitive_content(self, content, filename=""):
        """Filter out sensitive information from content"""
        if not content:
            return content

        # Always filter Discord tokens regardless of filename
        filtered_content = content

        # Filter Discord tokens
        filtered_content = re.sub(
            r'[A-Za-z0-9]{24}\.[A-Za-z0-9]{6}\.[A-Za-z0-9_\-]{27}',
            '[TOKEN_REDACTED]',
            filtered_content
        )

        # For config files, filter more aggressively
        if 'config' in filename.lower() or 'manager' in filename.lower():
            for pattern in self.sensitive_patterns[:-2]:
                filtered_content = re.sub(
                    pattern,
                    lambda m: self._replace_with_redacted(m),
                    filtered_content
                )

        return filtered_content

    def _replace_with_redacted(self, match):
        """Replace matched sensitive content with redacted version"""
        matched_text = match.group(0)
        if ':' in matched_text:
            key_part = matched_text.split(':')[0]
            return f'{key_part}: "[REDACTED]"'
        else:
            return '"[REDACTED]"'

    def _validate_file_path(self, path):
        """Ensure file operations stay within project directory"""
        project_root = str(pathlib.Path(__file__).parent.parent.resolve())
        requested_path = str(pathlib.Path(path).resolve())

        if not requested_path.startswith(project_root):
            raise ValueError("File operations restricted to project directory")
        return requested_path

    def _find_file(self, filename):
        """Search for a file recursively in the project directory"""
        project_root = pathlib.Path(__file__).parent.parent.resolve()

        # If it's already an absolute path within project
        try:
            full_path = pathlib.Path(filename).resolve()
            if str(full_path).startswith(str(project_root)) and full_path.exists():
                return str(full_path)
        except:
            pass

        # Search recursively for the file
        for root, dirs, files in os.walk(project_root):
            for file in files:
                if file == filename:
                    return os.path.join(root, file)

        # If not found, return the direct path (will cause FileNotFoundError)
        return os.path.join(project_root, filename)

    def _safe_open(self, path, mode='r', **kwargs):
        """Safe open function that filters content when reading"""
        validated_path = self._validate_file_path(path)
        filename = os.path.basename(validated_path)

        # Create a wrapper class for file operations
        class FilteredFile:
            def __init__(self, file_obj, filename, filter_func):
                self._file = file_obj
                self._filename = filename
                self._filter_func = filter_func
                self.mode = file_obj.mode

            def read(self, size=-1):
                content = self._file.read(size)
                if 'r' in self.mode:
                    return self._filter_func(content, self._filename)
                return content

            def readline(self, size=-1):
                line = self._file.readline(size)
                if 'r' in self.mode:
                    return self._filter_func(line, self._filename)
                return line

            def readlines(self, hint=-1):
                lines = self._file.readlines(hint)
                if 'r' in self.mode:
                    return [self._filter_func(line, self._filename) for line in lines]
                return lines

            def write(self, data):
                return self._file.write(data)

            def close(self):
                return self._file.close()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self._file.close()

            def __iter__(self):
                return self

            def __next__(self):
                line = next(self._file)
                if 'r' in self.mode:
                    return self._filter_func(line, self._filename)
                return line

        original_file = open(validated_path, mode, **kwargs)
        if 'r' in mode:
            return FilteredFile(original_file, filename, self._filter_sensitive_content)
        return original_file

    def _read_file(self, path: str):
        """Safe file reading method with recursive search and token filtering"""
        try:
            # Try to find the file first
            actual_path = self._find_file(path)
            filename = os.path.basename(actual_path)
            validated_path = self._validate_file_path(actual_path)
            with open(validated_path, 'r') as f:
                content = f.read()

            # Filter sensitive content
            filtered_content = self._filter_sensitive_content(content, filename)
            return filtered_content
        except FileNotFoundError:
            return f"Error: File '{path}' not found"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _edit_file(self, path: str, content: str):
        """Safe file editing method with recursive search"""
        try:
            # Try to find the file first
            actual_path = self._find_file(path)
            validated_path = self._validate_file_path(actual_path)
            with open(validated_path, 'w') as f:
                f.write(content)
            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    def _create_file(self, path: str, content: str = ""):
        """Safely create a file with optional content."""
        try:
            validated_path = self._validate_file_path(path)
            with open(validated_path, 'w') as f:
                f.write(content)
            return f"Successfully created {path}"
        except Exception as e:
            return f"Error creating file: {str(e)}"

    def _delete_file(self, path: str):
        """Safely delete a file with recursive search."""
        try:
            # Try to find the file first
            actual_path = self._find_file(path)
            validated_path = self._validate_file_path(actual_path)
            os.remove(validated_path)
            return f"Successfully deleted {path}"
        except FileNotFoundError:
            return f"Error: File '{path}' not found"
        except Exception as e:
            return f"Error deleting file: {str(e)}"

    def _insert_at_line(self, path: str, line_number: int, content: str):
        """Insert content at specific line number"""
        try:
            # Try to find the file first
            actual_path = self._find_file(path)
            validated_path = self._validate_file_path(actual_path)

            # Read existing content
            with open(validated_path, 'r') as f:
                lines = f.readlines()

            # Insert content at specified line (1-indexed)
            if line_number <= 0:
                line_number = 1
            elif line_number > len(lines) + 1:
                line_number = len(lines) + 1

            # Split content into lines and insert
            content_lines = content.split('\n')
            if content_lines and content_lines[-1] == '':
                content_lines.pop()

            # Insert lines at the specified position
            for i, line in enumerate(content_lines):
                lines.insert(line_number - 1 + i, line + ('\n' if i < len(content_lines) - 1 or content.endswith('\n') else ''))

            # Write back to file
            with open(validated_path, 'w') as f:
                f.writelines(lines)

            return f"Successfully inserted content at line {line_number} in {path}"
        except Exception as e:
            return f"Error inserting at line: {str(e)}"

    def _replace_line(self, path: str, line_number: int, new_content: str):
        """Replace content at specific line number"""
        try:
            # Try to find the file first
            actual_path = self._find_file(path)
            validated_path = self._validate_file_path(actual_path)

            # Read existing content
            with open(validated_path, 'r') as f:
                lines = f.readlines()

            # Check if line number is valid
            if line_number <= 0 or line_number > len(lines):
                return f"Error: Line {line_number} is out of range (file has {len(lines)} lines)"

            # Replace the line (1-indexed)
            lines[line_number - 1] = new_content + ('\n' if not new_content.endswith('\n') else '')

            # Write back to file
            with open(validated_path, 'w') as f:
                f.writelines(lines)

            return f"Successfully replaced line {line_number} in {path}"
        except Exception as e:
            return f"Error replacing line: {str(e)}"

    def _get_line(self, path: str, line_number: int):
        """Get content of specific line"""
        try:
            # Try to find the file first
            actual_path = self._find_file(path)
            filename = os.path.basename(actual_path)
            validated_path = self._validate_file_path(actual_path)

            # Read existing content
            with open(validated_path, 'r') as f:
                lines = f.readlines()

            # Check if line number is valid
            if line_number <= 0 or line_number > len(lines):
                return f"Error: Line {line_number} is out of range (file has {len(lines)} lines)"

            # Get the line content (1-indexed)
            content = lines[line_number - 1]

            # Filter sensitive content if needed
            filtered_content = self._filter_sensitive_content(content, filename)
            return filtered_content.rstrip('\n')
        except Exception as e:
            return f"Error getting line: {str(e)}"

    def _get_lines(self, path: str, start_line: int, end_line: int = None):
        """Get content of specific lines (start to end)"""
        try:
            # Try to find the file first
            actual_path = self._find_file(path)
            filename = os.path.basename(actual_path)
            validated_path = self._validate_file_path(actual_path)

            # Read existing content
            with open(validated_path, 'r') as f:
                lines = f.readlines()

            # Set end_line if not provided
            if end_line is None:
                end_line = start_line

            # Check if line numbers are valid
            if start_line <= 0 or start_line > len(lines):
                return f"Error: Start line {start_line} is out of range (file has {len(lines)} lines)"
            if end_line <= 0 or end_line > len(lines):
                return f"Error: End line {end_line} is out of range (file has {len(lines)} lines)"
            if start_line > end_line:
                return f"Error: Start line {start_line} cannot be greater than end line {end_line}"

            # Get the lines content (1-indexed)
            content_lines = lines[start_line - 1:end_line]
            content = ''.join(content_lines)

            # Filter sensitive content if needed
            filtered_content = self._filter_sensitive_content(content, filename)
            return filtered_content.rstrip('\n')
        except Exception as e:
            return f"Error getting lines: {str(e)}"

    @commands.command(name="eval")
    async def _eval(self, ctx, *, code: str = None):
        """Evaluate Python code with file access (Owner only)."""
        if not code:
            embed = discord.Embed(
                title="❌ Error",
                description="You must provide code to execute!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if ctx.author.id != YOUR_ID:
            embed = discord.Embed(
                title="🚫 Permission Denied",
                description="You don't have permission to use this command.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        import sys
        project_root = str(pathlib.Path(__file__).parent.parent.resolve())
        if project_root not in sys.path:
            sys.path.append(project_root)

        try:
            import utils.logger
            import utils.permissions
            utils_available = True
        except ImportError:
            utils_available = False

        # Define environment with file access
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self.bot._last_result,
            "os": os,
            "open": self._safe_open,
            "__import__": __import__,
            "utils_logger": __import__("utils.logger") if utils_available else None,
            "utils_permissions": __import__("utils.permissions") if utils_available else None,
            "read_file": self._read_file,
            "edit_file": self._edit_file,
            "create_file": self._create_file,
            "delete_file": self._delete_file,
            "insert_at_line": self._insert_at_line,
            "replace_line": self._replace_line,
            "get_line": self._get_line,
            "get_lines": self._get_lines,
            "validate_path": self._validate_file_path,
            "asyncio": asyncio,
            "print": lambda *args, **kwargs: print(*args, **kwargs)
        }
        env.update(globals())

        code = code.strip("` \n")
        if code.startswith("py"):
            code = code[2:]

        stdout = io.StringIO()
        to_compile = (
            'async def func():\n'
            '    import asyncio\n'
            f'{textwrap.indent(code, "    ")}\n'
            '    return locals().get("result")'
        )

        try:
            exec(to_compile, env)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Syntax Error",
                description=f"```py\n{e.__class__.__name__}: {e}\n```",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            embed = discord.Embed(
                title="❌ Runtime Error",
                description=f"```py\n{value}{traceback.format_exc()}\n```",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction("✅")
            except:
                pass

            result_str = ""
            if value:
                result_str += value

            if ret is not None:
                self.bot._last_result = ret
                if asyncio.iscoroutine(ret):
                    ret = await ret

                try:
                    if isinstance(ret, str):
                        result_str += ret
                    elif hasattr(ret, '__str__'):
                        result_str += str(ret)
                    else:
                        result_str += repr(ret)
                except Exception:
                    result_str += f"<{type(ret).__name__} object>"

            if result_str.strip():
                embed = discord.Embed(
                    title="✅ Execution Result",
                    description=f"```py\n{result_str}\n```",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                # Send empty success message if no output
                embed = discord.Embed(
                    title="✅ Execution Result",
                    description="Command executed successfully (no output)",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)

async def setup(bot):
    """Required setup function for Discord.py cogs"""
    await bot.add_cog(Eval(bot))
