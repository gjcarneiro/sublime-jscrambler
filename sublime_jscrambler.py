import sublime
import sublime_plugin
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    import jscrambler
except ImportError as ex:
    print("jscrambler python module is not available")
    jscrambler = None
    jscrambler_import_error = str(ex)

import tempfile
import shutil
import threading
import subprocess


def get_plugin_settings():
    setting_name = 'sublime_jscrambler.sublime-settings'
    plugin_settings = sublime.load_settings(setting_name)
    return plugin_settings


class JscramblerCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        thread = threading.Thread(target=self._run_async)
        thread.start()

    def _run_async(self):
        config = get_plugin_settings()
        filename = self.view.file_name()
        self.view.set_status("jscrambler", "Uploading JScrambler job...")
        try:
            tempdir = tempfile.mkdtemp()
            try:
                if config.get("use_external_tool"):
                    try:
                        argv = [config.get("external_tool"), tempdir, filename]
                        print(argv)
                        stderr = subprocess.check_output(
                            argv,
                            stderr=subprocess.STDOUT)
                    except subprocess.CalledProcessError as ex:
                        sublime.error_message(str(ex))
                        return
                    if stderr:
                        sublime.error_message(str(stderr))
                        return
                else:
                    if jscrambler is None:
                        sublime.error_message("The jscrambler Python module "
                                              "could not be imported ({0}): "
                                              "your only option is to set "
                                              "use_external_tool to true."
                                              .format(jscrambler_import_error))
                        return

                    client = jscrambler.Client(config.get("keys")["accessKey"],
                                               config.get("keys")["secretKey"],
                                               host=config.get("host"),
                                               port=config.get("port"))
                    params = config.get("params")
                    result = client.upload_code(filename, **params)
                    try:
                        project_id = result['id']
                    except KeyError:
                        sublime.error_message(str(result))
                        return
                    client.poll_project(project_id)
                    client.download_code(project_id, tempdir)

                outfile = os.path.join(tempdir,
                                       "." + os.path.splitdrive(filename)[1])
                with open(outfile, "rt") as outfileobj:
                    contents = outfileobj.read()
            finally:
                shutil.rmtree(tempdir)
            contents = """function D(){console.log("Hello world");};"""
            view = self.view.window().new_file()
            view.set_scratch(True)
            view.set_syntax_file('Packages/JavaScript/JavaScript.tmLanguage')
            view.run_command("jscrambler_insert_contents",
                             dict(contents=contents))
        finally:
            self.view.set_status("jscrambler", "")


class JscramblerInsertContentsCommand(sublime_plugin.TextCommand):
    def run(self, edit, contents):
        self.view.insert(edit, 0, contents)
