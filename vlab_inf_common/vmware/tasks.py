# -*- coding: UTF-8 -*-
"""
This module is for working with pyVmomi Task objects.
"""
import time


def consume_task(the_task, timeout=600):
    """Wait for a task to complete

    :Returns: vim.TaskInfo.result

    :Raises: RuntimeError

    :param the_task: The pyVmomi task that you're waiting on
    :type the_task: vim.Task

    :param timeout: How many seconds to wait for a task to complete
    :type timeout: Integer
    """
    for _ in range(timeout):
        if the_task.info.completeTime:
            break
        else:
            time.sleep(1)
    else:
        msg = 'Timeout of {} seconds exceeded for task {}'.format(timeout, the_task)
        raise RuntimeError(msg)
    if the_task.info.error:
        raise RuntimeError(the_task.info.error.msg)
    return the_task.info.result
