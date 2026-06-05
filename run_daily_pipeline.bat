@echo off

:: Установка кодировки UTF-8 для Python
set PYTHONIOENCODING=utf-8

:: Точный путь к файлу 
cd /d "C:\...\Project_LOL\run_daily_pipeline"   

echo ============================= >> pipeline.log
echo %date% %time% >> pipeline.log

echo Запуск riot_pipeline... >> pipeline.log
C:\ProgramData\anaconda3\python.exe riot_pipeline.py >> pipeline.log 2>&1

echo Запуск EDA... >> pipeline.log
C:\ProgramData\anaconda3\python.exe EDA.py >> pipeline.log 2>&1

echo Запуск dashboard_etl... >> pipeline.log
C:\ProgramData\anaconda3\python.exe dashboard_etl.py >> pipeline.log 2>&1

echo Выполнение завершено. >> pipeline.log
