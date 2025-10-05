curl  "https://us-central1-burner-board.cloudfunctions.net/boards/UpdateProfile/CoronaSign" -X POST -H "Content-Type: application/json" \
--data '{"video":[
        {"profile":"CoronaSign","algorithm":"simpleSign(Hello,blue,black)"},
        {"profile":"CoronaSign","algorithm":"simpleSign(Dr,red,black)"},
        {"profile":"CoronaSign","algorithm":"simpleSign(Save,yellow,purple)"},
        {"profile":"CoronaSign","algorithm":"simpleSign(Corona!,blue,black)"}
        ]}' \