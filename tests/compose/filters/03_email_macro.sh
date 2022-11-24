# Malicious macros should be blocked
# see https://github.com/clr2of8/VBAstomp and https://github.com/decalage2/oletools/wiki/mraptor
python3 tests/email_test.py message-macro-stomp "tests/compose/filters/2003x32_word_msgbox_stomped_fakecode.doc"
if [ $? -ne 25 ]; then
	exit 1
fi
# This does Auto_Open + Alert()
python3 tests/email_test.py message-autoexec-macro "tests/compose/filters/excel4_sample_macro.slk"
if [ $? -ne 25 ]; then
	exit 1
fi

exit 0
