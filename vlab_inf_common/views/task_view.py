# -*- coding: UTF-8 -*-
"""
TODO
"""
import ujson
from flask import current_app
from flask_classy import request, route
from vlab_api_common import describe, BaseView, requires, get_logger

logger = get_logger(__name__, loglevel='INFO')


class TaskView(BaseView):
    """Defines the ``/<route_base>/task`` end point for async API actions"""
    TASK_ARGS = { "$schema": "http://json-schema.org/draft-04/schema#",
	              "type": "object",
                  "properties": {
                     "task-id": {
                         "descrition": "The Task Id. Optionally index the URL with the task id",
                         "type": "string"
                     }
                   },
                   "required":[
                      "task-id"
                   ]
                }

    @route('/task', methods=["GET"])
    @route('/task/<tid>', methods=["GET"])
    @requires(verify=False, version=(1,2))
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
                logger.error("Task {} failed: {}".format(task_id, result.result))
                resp['error'] = result.result['error']
                return ujson.dumps(resp), 400
            return ujson.dumps(result.result), 200
        elif result.status == 'FAILURE':
            logger.error("Task {} errored: {}".format(task_id, result.result))
            return ujson.dumps(resp), 500
        else:
            return ujson.dumps(resp), 202
