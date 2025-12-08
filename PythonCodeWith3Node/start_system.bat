@REM Hend: I got windows and sometimes I use bat files to start multiple cmd windows for testing but it's the same if you ignore this file and run them manually

@echo off
echo Starting 3-Node Fault Tolerance Test System
echo.

echo Starting Coordination Layer...
start "Manager" cmd /k "python coordinationlayer.py"
timeout /t 3

echo Starting Node 1 (Normal)...
start "Node1" cmd /k "python launcher.py 1 normal 50"
timeout /t 2

echo Starting Node 2 (Normal)...  
start "Node2" cmd /k "python launcher.py 2 normal 52"
timeout /t 2

echo Starting Node 3 (Byzantine Fault)...
start "Node3" cmd /k "python launcher.py 3 byzantine 50"

echo.
echo All components started!
echo - Manager: Coordination layer with fault tolerance
echo - Node 1: Normal operation (50cm base)
echo - Node 2: Normal operation (52cm base) 
echo - Node 3: Byzantine faults (random readings)
echo.
echo Press any key to exit...
pause


