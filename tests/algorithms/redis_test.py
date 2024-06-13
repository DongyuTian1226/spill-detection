import redis
import time
import os
from multiprocessing import Process

# 连接 Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

def acquire_lock(lock_name, acquire_timeout=10):
    """ 尝试获取锁 """
    lock = redis_client.lock(lock_name, timeout=acquire_timeout)
    acquired = lock.acquire(blocking=True)
    return lock if acquired else None

def release_lock(lock):
    """ 释放锁 """
    if lock:
        lock.release()

def task(lock_name):
    """ 模拟任务执行 """
    lock = acquire_lock(lock_name)
    if lock:
        try:
            print(f"Process {os.getpid()} acquired lock. Performing task...")
            time.sleep(5)  # 模拟任务执行的耗时操作
        finally:
            release_lock(lock)
            print(f"Process {os.getpid()} released lock.")

if __name__ == '__main__':
    lock_name = "my_lock"

    # 创建多个进程执行任务
    processes = []
    for _ in range(3):  # 创建3个进程
        p = Process(target=task, args=(lock_name,))
        processes.append(p)
        p.start()

    # 等待所有进程完成
    for p in processes:
        p.join()
