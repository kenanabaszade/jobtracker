from aiogram import Router

from src.bot.handlers.commands import router as commands_router

main_router = Router()
main_router.include_router(commands_router)
