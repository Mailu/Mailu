python3 tests/email_test.py message-virus "tests/compose/filters/eicar.com.txt"
<<<<<<< HEAD
<<<<<<< HEAD
if [ $? -ne 25 ]; then
  exit 1
=======
if [ $? -eq 99 ]; then
    python3 tests/email_test.py message-PUA "tests/compose/filters/PotentiallyUnwanted.exe_"
    if [ $? -eq 99 ]; then
        exit 0
    else
        exit 1
    fi
else
	exit 1
>>>>>>> f7fb0f66 (Add a new test for PUAs)
fi
python3 tests/email_test.py message-PUA "tests/compose/filters/PotentiallyUnwanted.exe_"
if [ $? -ne 25 ]; then
=======
if [ $? -ne 99 ]; then
  exit 1
fi
python3 tests/email_test.py message-PUA "tests/compose/filters/PotentiallyUnwanted.exe_"
if [ $? -ne 99 ]; then
>>>>>>> 6765c45a (simplify)
  exit 1
fi

exit 0
