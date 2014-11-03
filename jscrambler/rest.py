# Copyright (c) 2013 Gustavo J. A. M. Carneiro  <gjcarneiro@gmail.com>

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""

REST wrappers for the jscrambler API.  This is a low level API,
and you probably wish to use jscrabler.Client instead.

"""


import requests
from datetime import datetime
from collections import OrderedDict
import hashlib
import hmac
import base64

try:
    from urlparse import urlparse
except ImportError:
    # Python 3
    from urllib.parse import urlparse, quote

try:
    from urllib import quote
except ImportError:
    # Python 3
    from urllib.parse import quote

import codecs

#API_HOSTNAME = "api.jscrambler.com"
#API_URL = "https://{0}/v3".format(API_HOSTNAME)

def _quote(value):
    value = quote(value)
    value = value.replace("%7E", "~")
    value = value.replace("+", "%20")
    value = value.replace("/", "%2F")
    return value


def _add_authentication(params, access_key, secret_key, method, url,
                        signature_parameters=None):
    params.extend([
        ("access_key", codecs.encode(access_key, "hex_codec").upper()),
        ("timestamp", datetime.now().isoformat()),
        ])

    if signature_parameters is None:
        signature_parameters = params
    else:
        signature_parameters = params + signature_parameters

    signature_parameters.sort()

    parsed_url = urlparse(url)
    request = '/' + parsed_url.path.split("/", 2)[2]
    api_hostname = parsed_url.hostname

    url_query_string = '&'.join("{0}={1}".format(name, _quote(value))
                                for name, value in signature_parameters)
    hmac_signature_data = ';'.join([method, api_hostname,
                                   request, url_query_string])
    sig = hmac.new(codecs.encode(secret_key, 'hex_codec').upper(),
                   msg=hmac_signature_data.encode("ascii"),
                   digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(sig).decode()
    params.append(('signature', signature))


def post(api_url, access_key, secret_key, files, **opt_params):
    """
    :param files: List of files to upload.  It can be either a list of file
        names or a list of (file_name, file_object) tuples.
    """
    params = list(opt_params.items())
    sig_params = []
    files_dict = {}
    for num, file_spec in enumerate(files):
        if type(file_spec) is tuple:
            fname, fobject = file_spec
        else:
            fname = file_spec
            fobject = open(fname, "rb")
        m = hashlib.md5()
        m.update(fobject.read())
        fobject.seek(0)
        sig_params.append(("file_" + str(num), m.hexdigest().lower()))
        files_dict["file_" + str(num)] = (fname, fobject)
    url = api_url + "/code.json"
    _add_authentication(params, access_key, secret_key, "POST", url,
                        signature_parameters=sig_params)
    r = requests.post(url, data=OrderedDict(sorted(params)), files=files_dict)
    return r.json()


def get_status(api_url, access_key, secret_key, status=None, offset=None,
               limit=None, **opt_params):
    params = opt_params.items()
    if status is not None:
        params.append(('status', str(status)))
    if offset is not None:
        params.append(('offset', str(offset)))
    if limit is not None:
        params.append(('limit', str(limit)))
    url = api_url + "/code.json"
    _add_authentication(params, access_key, secret_key, "GET", url)
    r = requests.get(url, params=OrderedDict(sorted(params)))
    return r.json()


def get_project_status(api_url, access_key, secret_key, project_id,
                       symbol_table=None, **opt_params):
    url = api_url + '/code/{0}.json'.format(project_id)
    params = list(opt_params.items())
    if symbol_table is not None:
        params.append(('symbol_table', str(symbol_table)))
    _add_authentication(params, access_key, secret_key, "GET", url)
    r = requests.get(url, params=OrderedDict(sorted(params)))
    return r.json()


def get_project_zip(api_url, access_key, secret_key, project_id, **opt_params):
    """
    output_file: a file name or file object
    """
    url = api_url + '/code/{0}.zip'.format(project_id)
    params = list(opt_params.items())
    _add_authentication(params, access_key, secret_key, "GET", url)
    r = requests.get(url, params=OrderedDict(sorted(params)))
    if r.status_code == requests.codes.ok:
        return r.content
    else:
        raise RuntimeError


def get_project_source_info(api_url, access_key, secret_key, project_id,
                            source_id, **opt_params):
    url = api_url + '/code/{0}/{1}.json'.format(project_id, source_id)
    params = list(opt_params.items())
    _add_authentication(params, access_key, secret_key, "GET", url)
    r = requests.get(url, params=OrderedDict(sorted(params)))
    return r.json()


def get_project_source(api_url, access_key, secret_key, project_id, source_id,
                       extension, **opt_params):
    url = api_url + '/code/{0}/{1}.{2}'.format(project_id, source_id, extension)
    params = list(opt_params.items())
    _add_authentication(params, access_key, secret_key, "GET", url)
    r = requests.get(url, params=OrderedDict(sorted(params)))
    return r.text


def delete_project(api_url, access_key, secret_key, project_id, **opt_params):
    url = api_url + '/code/{0}.json'.format(project_id)
    params = list(opt_params.items())
    _add_authentication(params, access_key, secret_key, "DELETE", url)
    r = requests.delete(url, params=OrderedDict(sorted(params)))
    return r.json()


