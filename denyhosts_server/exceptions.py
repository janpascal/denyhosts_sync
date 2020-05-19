# denyhosts sync server
# Copyright (C) 2020 Jan-Pascal van Best <janpascal@vanbest.org>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

from aiohttp_xmlrpc.exceptions import XMLRPCError, register_exception

logger = logging.getLogger(__name__)

class IllegalIPAddressException(XMLRPCError):
    code = 101
   
class IllegalParametersException(XMLRPCError):
    code = 102

class IllegalTimestampException(XMLRPCError):
    code = 103
   
class ErrorAddingHostsException(XMLRPCError):
    code = 104

class GetNewHostsException(XMLRPCError):
    code = 105

class UnknownCrackerException(XMLRPCError):
    code = 106

def register_exceptions():
    register_exception(IllegalIPAddressException, IllegalIPAddressException.code)
    register_exception(IllegalParametersException, IllegalParametersException.code)
    register_exception(IllegalTimestampException, IllegalTimestampException.code)
    register_exception(ErrorAddingHostsException, ErrorAddingHostsException.code)
    register_exception(GetNewHostsException, GetNewHostsException.code)
    register_exception(UnknownCrackerException, UnknownCrackerException.code)

