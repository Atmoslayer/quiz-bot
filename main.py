def main():
    quiz = {}
    with open('questions/1vs1200.txt', 'r', encoding='KOI8-R') as file:
        question_number = 1
        question_title = ''
        for line in file:
            line = line.replace('\n', '')
            if 'Вопрос' in line:
                question_title = f'Вопрос {question_number}'
                question = ''
                line = next(file)
                while not line == '\n':
                    question += line
                    line = next(file)
                quiz.setdefault(question_title, [])
                quiz[question_title].append(question)
                question_number += 1
            elif 'Ответ' in line:
                answer = ''
                line = next(file)
                while not line == '\n':
                    answer += line
                    line = next(file)
                quiz.setdefault(question_title, [])
                quiz[question_title].append(answer)

if __name__ == '__main__':
    main()
