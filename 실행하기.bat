@echo off
title 현대재고관리 서버 실행중
echo [현대재고관리 시스템을 시작합니다...]
echo.
echo 1. 서버를 가동합니다.
echo 2. 잠시 후 브라우저가 자동으로 열립니다.
echo.
echo ※ 이 창을 닫으면 프로그램이 종료됩니다. 작업을 마칠 때까지 닫지 마세요.
echo.

start http://localhost:3000
node server.js
pause
