import inquirer
from loguru import logger


class Menu:
    @staticmethod
    def open_menu(accounts_length: int, proxies_length: int):
        print('''
╭╮╱╭╮╱╱╱╱╱╭╮╱╭━━━╮╱╱╱╱╱╱╱╱╭╮
┃┃╱┃┃╱╱╱╱╱┃┃╱┃╭━╮┃╱╱╱╱╱╱╱╭╯╰╮
┃╰━╯┣━━┳━━┫┃╭┫┃╱┃┣╮╭┳━━┳━┻╮╭╯
┃╭━╮┃╭╮┃╭━┫╰╯┫┃╱┃┃┃┃┃┃━┫━━┫┃
┃┃╱┃┃╭╮┃╰━┫╭╮┫╰━╯┃╰╯┃┃━╋━━┃╰╮
╰╯╱╰┻╯╰┻━━┻╯╰┻━━╮┣━━┻━━┻━━┻━╯
╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╰╯
╭━━━╮╱╱╱╭━┳╮╱╭╮
┃╭━╮┃╱╱╱┃╭╯╰╮┃┃
┃╰━━┳━━┳╯╰╮╭╯┃╰━┳╮╱╭╮╭━━┳┳━━╮
╰━━╮┃╭╮┣╮╭┫┃╱┃╭╮┃┃╱┃┃┃╭╮┣┫╭╮┃
┃╰━╯┃╰╯┃┃┃┃╰╮┃╰╯┃╰━╯┃┃╭╮┃┃╰╯┃
╰━━━┻━━╯╰╯╰━╯╰━━┻━╮╭╯╰╯╰┻┻━━╯
╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╭━╯┃
╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╰━━╯\n''')
        
        lines = [
            f"Total accs loaded: {accounts_length}",
            f"Total proxies loaded: {proxies_length}",
            "",
            "Telegram channel: https://t.me/touchingcode",
        ]

        max_len = max(len(line) for line in lines)
        width = max_len + 2

        print("+" + "-" * (width + 2) + "+")
        for line in lines:
            print("| " + line.ljust(width) + " |")
        print("+" + "-" * (width + 2) + "+")


        questions = [
            inquirer.List('first_choice', message="Make a choice", choices=['Start', 'Quit']),
        ]

        answer = inquirer.prompt(questions)
        if not answer:
            logger.error('Failed to get first answer')
            return False
        if answer.get('first_choice') == 'Quit':
            logger.info('Quitting...')
            return False
            
        if answer.get('first_choice') == 'Start':
            logger.info('Starting...')
            return True
