cd ..
if not exist bin mkdir bin
cd builds
call build_ch.bat
cd builds
call build_en.bat
cd builds
call build_chart.bat