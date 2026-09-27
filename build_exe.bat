@echo off
chcp 65001 > nul
echo =====================================================================
echo    COMPILADOR DE EXECUTÁVEL - SISTEMA DE GESTÃO DE VENDAS (PDV)
echo =====================================================================
echo.

echo [1/3] Verificando dependências no ambiente Python...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao verificar/instalar dependências.
    pause
    exit /b %errorlevel%
)

echo.
echo [2/3] Compilando executável com PyInstaller...
echo Comando: python -m PyInstaller --noconfirm --onefile --windowed --name "GestaoVendas" --add-data "assets;assets" --collect-all customtkinter app.py
echo.

python -m PyInstaller --noconfirm --onefile --windowed --name "GestaoVendas" --add-data "assets;assets" --collect-all customtkinter app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Ocorreu um erro durante o processo de compilação.
    pause
    exit /b %errorlevel%
)

echo.
echo =====================================================================
echo    SUCESSO! Executável gerado com êxito!
echo    Local: dist\GestaoVendas.exe
echo =====================================================================
echo.
pause
