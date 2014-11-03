"""
High level API for JScrambler.
"""

__all__ = ["Client"]

from glob import glob
import os.path
import logging
import json
try:
    from cStringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO
from zipfile import ZipFile
import time
import codecs

LOG = logging.getLogger("jscrambler")

import jscrambler.rest


try:
    # Python 2
    text_types = basestring
except NameError:
    # Python 3
    text_types = (str,)


class Client(object):
    """
    Communicate with the jscrambler server.

    This provides a high level API to the jscrambler service.  Get your API
    credentials at https://jscrambler.com/en/account/api_access.

    :param accessKey: the "access key" credential, obtainable from the
        jscrambler account dashboard
    :param secretKey: the "secret key" credential, obtainable from the
        jscrambler account dashboard
    :param host: the jscrambler server hostname.  Leaving the default value
        is recommended.
    :param port: the jscrambler server port.  Leaving the default value
        is recommended.
    :param apiVersion: the jscrambler REST API version.  Leaving the default
        value is recommended.


    """
    def __init__(self, accessKey, secretKey,
                 host='api.jscrambler.com',
                 port=443,
                 apiVersion=3):
        if port == 443:
            self.api_url = "https://{host}/v{ver}".format(host=host,
                                                          ver=apiVersion)
        else:
            self.api_url = "http://{host}:{port}/v{ver}".format(host=host,
                                                                 port=port,
                                                                 ver=apiVersion)
        print("URL:", self.api_url)
        LOG.debug("jscrambler API URL: %s", self.api_url)
        self.access_key = codecs.decode(accessKey.encode("ascii"), "hex_codec")
        self.secret_key = codecs.decode(secretKey.encode("ascii"), "hex_codec")

    def upload_code(self, files_src, **params):
        """Uploads a project by zipping it and sending to the services.

        :param files_src: File or list of files to upload.  Wildcard (glob)
            patterns are supported. See :ref:`filesSrc`.
        :type files_src: str or list of str

        :param params: Additional named arguments are accepted and passed as
            parameters to the jscrambler server.
            For for information on supported parameters, consult
            the `WebAPI upload documentation`_

        :returns: a JSON object containing the server response, as
                  described in the `WebAPI upload documentation`_.
                  If no error has occurred, the value of the ``id``
                  key in the returned dict will contain the
                  ``project_id`` identifier, which can be used for
                  subsequent polling and dowloading operations.

        .. _WebAPI upload documentation: https://jscrambler.com/en/help/webapi/documentation#upload_code

        """
        if isinstance(files_src, text_types):
            files_src = [files_src]
        file_mem = StringIO()
        zip_file = ZipFile(file_mem, "w")
        for src in files_src:
            for fname in glob(src):
                fname = os.path.normpath(fname)
                zip_file.write(fname)
        zip_file.close()
        file_mem.seek(0)

        retval = jscrambler.rest.post(self.api_url,
                                      self.access_key,
                                      self.secret_key,
                                      [("project.zip", file_mem)],
                                      **params)
        LOG.debug("jscrambler post returned %r", retval)
        return retval

    def get_info(self, project_id=None):
        """Gets the information of client project(s).

        You can get information about your projects and project
        sources. This is useful to check project status, obtain
        detailed information about syntax errors found on a specific
        project source, etc.

        :param project_id: if not None, return information only on the project
            identified by this value, instead of all projects.

        :returns: a dict (if project_id is not None), or a list of dicts
            (if project_id is None).  Each dict contains  information about
            a project, with the following elements:

          id
              Unique identifier for this JavaScript project.

          error_message
              Short message about the result of obfuscation.

          received_at
              Date when the JavaScript project was uploaded.

          finished_at
              Date when JScrambler finished processing the JavaScript project.

          js_files
              Number of JavaScript source files.

          html_files
              Number of HTML source files.

        """
        if project_id is None:
            return jscrambler.rest.get_status(self.api_url,
                                              self.access_key,
                                              self.secret_key)
        else:
            return jscrambler.rest.get_project_status(self.api_url,
                                                      self.access_key,
                                                      self.secret_key,
                                                      project_id)

    def poll_project(self, project_id, maximum_poll_retries=10,  poll_pause=1):
        """
        Polls a project until it has finished processing.

        Raises RuntimeError in case of error.

        :param project_id: the ID of the project, as returned by
            :meth:`jscrambler.Client.upload_code`
        :param maximum_poll_retries: maximum number of additional retries
            if the project is not finished yet
        :param poll_pause: amount of time, in seconds, to sleep between
            polling retries

        :returns: the project status, as a dict in the format described in
            :meth:`jscrambler.Client.get_info`
        """
        for dummy in range(1, maximum_poll_retries + 2):
            status = jscrambler.rest.get_project_status(self.api_url,
                                                        self.access_key,
                                                        self.secret_key,
                                                        project_id)
            if status['finished_at'] is None:
                time.sleep(poll_pause)
                continue
            if project_id != status['id']:
                raise AssertionError("wrong project ID, expected {0} got {1}"
                                     .format(project_id, status['id']))
            if status.get("error_id", '0') != '0':
                raise RuntimeError(status)
            return status
        raise RuntimeError("timeout")

    def download_code(self, project_id, files_dest, source_id=None):
        """
        Downloads an entire project or a single source from a project

        :param project_id: the ID of the project, as returned by
            :meth:`jscrambler.Client.upload_code`
        :param filesDest: output directory under which the project files will
            be placed
        :param source_id: FIXME: not used yet

        """
        if not os.path.isdir(files_dest):
            raise ValueError("output directory {!r} does not exist"
                             .format(files_dest))

        zip_contents = jscrambler.rest.get_project_zip(self.api_url,
                                                       self.access_key,
                                                       self.secret_key,
                                                       project_id)
        zip_file = ZipFile(StringIO(zip_contents))
        zip_file.extractall(files_dest)

        jscrambler.rest.delete_project(self.api_url,
                                       self.access_key,
                                       self.secret_key,
                                       project_id)


    def process(self, config):
        """Executes the normal use case (upload_code + poll_project +
        download_code) given a path to a configuration file or a
        configuration object.

        :param config: configuration. If it is a string, it is taken as the
            name of a json configuration file to read. Else it should be a dict
            containing the configuration, following the same JSON structure.
            For more information, see :doc:`configuration`.
        :type config: dict or str

        """
        # if config is a file name, read json from it
        if isinstance(config, text_types):
            with open(config, "r") as jsonfile:
                config = json.load(jsonfile)

        upload_result = self.upload_code(config['filesSrc'],
                                         **config.get("params", {}))
        project_id = upload_result['id']

        self.poll_project(project_id)

        self.download_code(project_id, config['filesDest'])

