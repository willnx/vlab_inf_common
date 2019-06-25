# -*- coding: UTF-8 -*-
"""
Defines the API for common infrastructure API end points
"""
from abc import abstractmethod

import ujson
from flask import current_app
from flask_classy import request, route, Response
from vlab_api_common import describe, BaseView, requires, get_logger, validate_input

from vlab_inf_common.constants import const

logger = get_logger(__name__, loglevel='INFO')


class TaskView(BaseView):
    """Defines the ``/<route_base>/task`` end point for async API actions"""
    TASK_ARGS = { "$schema": "http://json-schema.org/draft-04/schema#",
	              "type": "object",
                  "properties": {
                     "task-id": {
                         "description": "The Task Id. Optionally index the URL with the task id",
                         "type": "string"
                     }
                   },
                   "required":[
                      "task-id"
                   ]
                }

    @route('/task', methods=["GET"])
    @route('/task/<tid>', methods=["GET"])
    @requires(verify=const.VLAB_VERIFY_TOKEN, version=2)
    @describe(get_args=TASK_ARGS)
    def handle_task(self, *args, **kwargs):
        """End point for checking the status of Celery tasks

        This end point will be called alot, the task-id is a random UUID, and
        it's really just checking the status, so there's no real security benefit
        to setting ``verify=True`` on the ``requires`` decorator.
        """
        resp = {'user': kwargs['token']['username'], 'content' : {}}
        if request.args.get('task-id', None) and kwargs.get('tid', None):
            resp['error'] = 'task-id supplied in URL and as param'
            return ujson.dumps(resp), 400

        task_id = request.args.get('task-id', kwargs.get('tid', None))
        if task_id is None:
            resp['error'] = "no task id provided"
            return ujson.dumps(resp), 400

        result = current_app.celery_app.AsyncResult(task_id)
        resp['content']['status'] = result.status
        if result.status == 'SUCCESS':
            resp.update(result.result)
            # All Celery Tasks MUST return a dictionary that has an "error" key.
            # We use this to determine if the task was OK, the user supplied bad
            # input, or there's a system failure when running the task.
            if result.result['error']:
                resp['error'] = result.result['error']
                return ujson.dumps(resp), 400
            return ujson.dumps(result.result), 200
        elif result.status == 'FAILURE':
            return ujson.dumps(resp), 500
        else:
            return ujson.dumps(resp), 202


class MachineView(TaskView):
    """Defines an asynchronous API for interacting with virtual machines in vLab.

    When subclassing this view, make sure to define the ``RESROUCE`` attribute.
    Failing to do so will result in requests not being forwarded to the backend
    workers.

    :attr RESOURCE: The name of the component/type of virtual machine
    :type RESROUCE: String
    """
    RESOURCE = None
    NETWORK_SCHEMA = {"$schema": "http://json-schema.org/draft-04/schema#",
	                  "type": "object",
                      "properties": {
                         "name": {
                            "description": "The name of the virtual machine",
                            "type": "string",
                         },
                         "new_network": {
                            "description": "The name of the network to connect the VM to",
                            "type": "string"
                         }
                      },
                      "required": ["name", "new_network"]
                     }

    @route('/network', methods=["PUT"])
    @requires(verify=const.VLAB_VERIFY_TOKEN, version=2)
    @validate_input(schema=NETWORK_SCHEMA)
    @describe(put=NETWORK_SCHEMA)
    def modify_network(self, *args, **kwargs):
        """Change the network a virtual machine is connected to"""
        username = kwargs['token']['username']
        machine_name = kwargs['body']['name']
        new_network = '{}_{}'.format(username, kwargs['body']['new_network'])
        txn_id = request.headers.get('X-REQUEST-ID', 'noId')
        resp_data = {'user' : username}
        task = current_app.celery_app.send_task('{}.modify_network'.format(self.RESOURCE.lower()),
                                                [username, machine_name, new_network, txn_id])
        resp_data['content'] = {'task-id': task.id}
        resp = Response(ujson.dumps(resp_data))
        resp.status_code = 202
        resp.headers.add('Link', '<{0}{1}/task/{2}>; rel=status'.format(const.VLAB_URL, self.route_base, task.id))
        return resp
