def get_quiz(questions_path):
    quiz = {}
    with open(f'{questions_path}', 'r', encoding='KOI8-R') as file:
        question = ''
        for line in file:
            line = line.replace('\n', '')
            if 'Вопрос' in line:
                question = ''
                line = next(file)
                while not line == '\n':
                    question += line.replace('\n', ' ')
                    line = next(file)
            elif 'Ответ' in line:
                answer = ''
                line = next(file)
                while not line == '\n':
                    answer += line.replace('\n', ' ')
                    line = next(file)
                quiz[question] = answer
    return quiz