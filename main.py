import config
from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils import deep_linking
from quiz import *

bot = Bot(token=config.TOKEN)
dp = Dispatcher(bot)

quiz_db = {}  # quiz info
quiz_owners = {}  # quiz owners info

# Хэндлер на команду /start


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    if message.chat.type == types.ChatType.PRIVATE:
        poll_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        poll_keyboard.add(types.KeyboardButton(
            text="Create quiz",
            request_poll=types.KeyboardButtonPollType(type=types.PollType.QUIZ)
        ))
        poll_keyboard.add(types.KeyboardButton(text="Cancel"))
        await message.answer("Push the button and create quiz!",
                             reply_markup=poll_keyboard)
    else:
        words = message.text.split()
        if len(words) == 1:
            bot_info = await bot.get_me()
            keyboard = types.InlineKeyboardMarkup()
            move_to_pm_button = types.InlineKeyboardButton(
                text="Go to bot",
                url=f"t.me/{bot_info.username}?start=anything"
            )
            keyboard.add(move_to_pm_button)
            await message.reply("No quiz selected. Go to bot to create quiz",
                                reply_markup=keyboard)
        else:
            quiz_owner = quiz_owners.get(words[1])
            if not quiz_owner:
                await message.reply('Invalid quiz. Try to create another one.')
                return
            for quiz in quiz_db[quiz_owner]:
                if quiz.quiz_id == words[1]:
                    msg = await bot.send_poll(
                        chat_id=message.chat.id,
                        question=quiz.question,
                        is_anonymous=False,
                        options=quiz.options,
                        type="quiz",
                        correct_option_id=quiz.correct_option_id
                    )
                    quiz_owners[msg.poll.id] = quiz_owner
                    del quiz_owners[words[1]]
                    quiz.quiz_id = msg.poll.id
                    quiz.chat_id = msg.chat.id
                    quiz.message_id = msg.message_id

# Хэндлер на текстовое сообщение "Отмена"


@dp.message_handler(lambda message: message.text == "Cancel")
async def action_cancel(message: types.Message):
    remove_keyboard = types.ReplyKeyboardRemove()
    await message.answer("The action canceled. Type /start to launch again",
                         reply_markup=remove_keyboard)


@dp.message_handler(content_types=["poll"])
async def msg_with_poll(message: types.Message):
    user_id = str(message.from_user.id)
    # if user is unknown
    if not quiz_db.get(user_id):
        quiz_db[user_id] = []

    # quiz type check
    if message.poll.type != "quiz":
        await message.reply("Sorry, I can get only quizes!")
        return

    # quiz saving
    quiz_db[user_id].append(Quiz(
        quiz_id=message.poll.id,
        question=message.poll.question,
        options=[o.text for o in message.poll.options],
        correct_option_id=message.poll.correct_option_id,
        owner_id=user_id
    ))
    quiz_owners[message.poll.id] = user_id

    await message.reply(
        f"Quiz saved. Total quiz count: {len(quiz_db[user_id])}"
    )


@dp.inline_handler()
async def inline_query(query: types.InlineQuery):
    results = []
    user_quizes = quiz_db.get(str(query.from_user.id))
    if user_quizes:
        for quiz in user_quizes:
            keyboard = types.InlineKeyboardMarkup()
            start_quiz_button = types.InlineKeyboardButton(
                text="Send to group",
                url=await deep_linking.get_startgroup_link(quiz.quiz_id)
            )
            keyboard.add(start_quiz_button)
            results.append(types.InlineQueryResultArticle(
                id=quiz.quiz_id,
                title=quiz.question,
                input_message_content=types.InputTextMessageContent(
                    message_text="Send button below to send quiz to group"
                ),
                reply_markup=keyboard
            ))
    await query.answer(switch_pm_text="Create quiz", switch_pm_parameter="_",
                       results=results, cache_time=120, is_personal=True)


@dp.poll_answer_handler()
async def handle_poll_answer(quiz_answer: types.PollAnswer):
    """
    Handler for new quiz answers
    * quiz_answer - active quiz answer
    :param quiz_answer: PollAnswer object with user info
    """
    quiz_owner = quiz_owners.get(quiz_answer.poll_id)
    if not quiz_owner:
        print(
            f"There is no quiz with quiz_answer.poll_id = {quiz_answer.poll_id}")
        return
    for quiz in quiz_db[quiz_owner]:
        if quiz.quiz_id == quiz_answer.poll_id:
            if quiz.correct_option_id == quiz_answer.option_ids[0]:
                quiz.winners.append(quiz_answer.user.id)
                if len(quiz.winners) == 3:
                    await bot.stop_poll(quiz.chat_id, quiz.message_id)


@dp.poll_handler(lambda active_quiz: active_quiz.is_closed is True)
async def just_poll_answer(active_quiz: types.Poll):
    """
    Action on quiz close
    :param active_quiz - active closed quiz 
    """
    quiz_owner = quiz_owners.get(active_quiz.id)
    if not quiz_owner:
        print(f"There is no quiz with active_quiz.id = {active_quiz.id}")
        return
    for num, quiz in enumerate(quiz_db[quiz_owner]):
        if quiz.quiz_id == active_quiz.id:
            congrats_text = []
            for winner in quiz.winners:
                chat_member_info = await bot.get_chat_member(quiz.chat_id, winner)
                congrats_text.append(
                    chat_member_info.user.get_mention(as_html=True))
            await bot.send_message(quiz.chat_id,
                                   "Quiz is over! List of winners:\n\n" +
                                   "\n".join(congrats_text),
                                   parse_mode="HTML"
                                   )
            del quiz_owners[active_quiz.id]
            del quiz_db[quiz_owner][num]

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
