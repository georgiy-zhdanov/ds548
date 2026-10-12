# judge_runner.py
import os
import signal
import tempfile
import subprocess
import threading
import queue
import time
from dataclasses import dataclass


@dataclass
class StreamResult:
    chunks: list
    size: int = 0


def _stream_reader(pipe, out_q: queue.Queue, stream_name: str, chunk_size: int = 4096):
    """Читает bytes из pipe чанками и отправляет в очередь."""
    try:
        while True:
            data = pipe.read(chunk_size)
            if not data:
                break
            out_q.put((stream_name, data))
    finally:
        out_q.put((stream_name, None))  # EOF marker


def _collect_with_limits(
    proc,
    container_name: str,
    force_remove_container,
    output_limit_bytes: int,
    deadline_monotonic: float,
):
    """
    Пороговое чтение stdout/stderr + ранний kill при OLE/TLE.
    Возвращает:
      status: 'ok' | 'ole' | 'tle'
      stdout_text, stderr_text, returncode, message
    """
    q = queue.Queue()
    stdout_res = StreamResult(chunks=[])
    stderr_res = StreamResult(chunks=[])

    t_out = threading.Thread(target=_stream_reader, args=(proc.stdout, q, "stdout"), daemon=True)
    t_err = threading.Thread(target=_stream_reader, args=(proc.stderr, q, "stderr"), daemon=True)
    t_out.start()
    t_err.start()

    eof_count = 0
    killed_reason = None

    while True:
        # TLE по внешнему дедлайну (доп. защита)
        if time.monotonic() > deadline_monotonic and proc.poll() is None:
            killed_reason = "tle"
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            force_remove_container(container_name)
            break

        try:
            stream_name, data = q.get(timeout=0.1)
        except queue.Empty:
            # если процесс завершился и потоки дочитаны - выйдем на EOF
            if proc.poll() is not None and not t_out.is_alive() and not t_err.is_alive():
                break
            continue

        if data is None:
            eof_count += 1
            if eof_count == 2:
                break
            continue

        if stream_name == "stdout":
            stdout_res.chunks.append(data)
            stdout_res.size += len(data)
            if stdout_res.size > output_limit_bytes:
                killed_reason = "ole"
        else:
            stderr_res.chunks.append(data)
            stderr_res.size += len(data)
            if stderr_res.size > output_limit_bytes:
                killed_reason = "ole"

        if killed_reason == "ole":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            force_remove_container(container_name)
            break

    # Финализация процесса
    try:
        proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass
        force_remove_container(container_name)

    try:
        if proc.stdout:
            proc.stdout.close()
    except Exception:
        pass

    try:
        if proc.stderr:
            proc.stderr.close()
    except Exception:
        pass

    stdout = b"".join(stdout_res.chunks).decode("utf-8", errors="replace")
    stderr = b"".join(stderr_res.chunks).decode("utf-8", errors="replace")
    returncode = proc.poll()

    if killed_reason == "ole":
        return "ole", stdout, stderr, returncode, "Output limit exceeded"
    if killed_reason == "tle":
        return "tle", stdout, stderr, returncode, "Time limit exceeded"

    # timeout внутри контейнера (GNU timeout) обычно возвращает 124
    if returncode == 124:
        return "tle", stdout, stderr, returncode, "Time limit exceeded"

    return "ok", stdout, stderr, returncode, ""


def check_code_submission(submission, problem, tests):
    """
    Универсальная проверка.
    tests: список тестов (уже полученный снаружи), где у каждого есть:
      - input_data
      - expected_output
    """
    if not tests:
        return 'error', 0, {'message': 'Нет тестов для проверки'}

    passed = 0
    total = len(tests)
    details = []

    image = "python:3.11-slim"
    memory_limit_mb = 256
    output_limit_bytes = 1_000_000
    time_limit = int(problem.time_limit)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp', encoding='utf-8') as f:
        f.write(submission.code)
        temp_file = f.name

    def force_remove_container(name: str):
        try:
            subprocess.run(
                ["/usr/bin/docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3
            )
        except Exception:
            pass

    try:
        for i, test in enumerate(tests, 1):
            container_name = f"judge_{submission.id}_{i}"
            proc = None

            try:
                with tempfile.TemporaryDirectory(prefix="judge_") as workdir:
                    solution_path = os.path.join(workdir, "solution.py")
                    input_path = os.path.join(workdir, "input.txt")

                    with open(temp_file, "r", encoding="utf-8") as src, \
                         open(solution_path, "w", encoding="utf-8") as dst:
                        dst.write(src.read())

                    with open(input_path, "w", encoding="utf-8") as inp:
                        inp.write(test.input_data or "")

                    os.chmod(workdir, 0o755)
                    os.chmod(solution_path, 0o644)
                    os.chmod(input_path, 0o644)

                    inner_cmd = (
                        f"timeout {time_limit}s "
                        f"python3 -I -B /workspace/solution.py < /workspace/input.txt"
                    )

                    docker_cmd = [
                        "/usr/bin/docker", "run", "--rm", "--init",
                        "--name", container_name,
                        "--network", "none",
                        "--read-only",
                        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                        "--cpus", "1.0",
                        "--memory", f"{memory_limit_mb}m",
                        "--memory-swap", f"{memory_limit_mb}m",
                        "--pids-limit", "64",
                        "--ulimit", "nofile=64:64",
                        "--security-opt", "no-new-privileges",
                        "--cap-drop", "ALL",
                        "--user", "65534:65534",
                        "--stop-timeout", "1",
                        "-v", f"{workdir}:/workspace:ro",
                        "-w", "/workspace",
                        image,
                        "sh", "-c", inner_cmd,
                    ]

                    proc = subprocess.Popen(
                        docker_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        preexec_fn=os.setsid
                    )

                    deadline = time.monotonic() + time_limit + 3  # host watchdog
                    status, stdout, stderr, rc, msg = _collect_with_limits(
                        proc=proc,
                        container_name=container_name,
                        force_remove_container=force_remove_container,
                        output_limit_bytes=output_limit_bytes,
                        deadline_monotonic=deadline
                    )

                if status == "ole":
                    details.append({'test': i, 'status': 'output_limit_exceeded', 'message': msg})
                    continue

                if status == "tle":
                    details.append({'test': i, 'status': 'time_limit_exceeded', 'message': msg})
                    continue

                if rc == 137:
                    details.append({'test': i, 'status': 'memory_limit_exceeded'})
                    continue

                if rc == 125:
                    details.append({'test': i, 'status': 'sandbox_error', 'message': 'Docker run failed'})
                    continue

                if rc in (126, 127):
                    details.append({'test': i, 'status': 'sandbox_error', 'message': 'Command not found'})
                    continue

                if rc != 0:
                    details.append({
                        'test': i,
                        'status': 'runtime_error',
                        'message': (stderr.strip() or f'exit code {rc}')[:200]
                    })
                    continue

                actual = stdout.strip()
                expected = (test.expected_output or "").strip()

                if actual == expected:
                    passed += 1
                    details.append({'test': i, 'status': 'passed'})
                else:
                    details.append({
                        'test': i,
                        'status': 'wrong_answer',
                        'expected': expected[:100],
                        'actual': actual[:100] if actual else '(пусто)'
                    })

            except FileNotFoundError:
                if proc and proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except Exception:
                        pass
                force_remove_container(container_name)
                details.append({'test': i, 'status': 'sandbox_error', 'message': 'docker not found'})

            except Exception as e:
                if proc and proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except Exception:
                        pass
                force_remove_container(container_name)
                details.append({'test': i, 'status': 'runtime_error', 'message': str(e)[:200]})

    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    score = round((passed / total) * problem.max_score) if total > 0 else 0
    
    # Определяем общий статус
    if passed == total:
        status = 'accepted'
    elif passed > 0:
        status = 'partial'
    else:
        # Все тесты упали — определяем статус по самой частой ошибке
        error_counts = {}
        for d in details:
            if d['status'] != 'passed':
                error_counts[d['status']] = error_counts.get(d['status'], 0) + 1
        
        if error_counts:
            status = max(error_counts, key=error_counts.get)
        else:
            status = 'wrong_answer'
    
    return status, score, {'tests': details, 'passed': passed, 'total': total}  