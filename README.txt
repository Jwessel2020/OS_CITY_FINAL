OS City V2 Simulation
There is no bullshit because it was all removed

How to Run:

To start the simulation server and dashboard, run the following command from the project root directory:

    python GP/V2/main_v2.py

Once running, the dashboard will be available at: http://127.0.0.1:8050

Troubleshooting:

If you encounter bugs, the server hangs, or you are unable to restart the simulation because the connection is in use, you may need to force kill the python processes.

On Windows, run:

    taskkill /IM python.exe /F

About pycache Folders

- Purpose: They make your program start faster on subsequent runs by skipping the compilation step for files that haven't changed.
