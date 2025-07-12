import pytz
import time
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from strategy import OpeningStrategy


timzone = pytz.timezone('UTC')
ops = OpeningStrategy('WMMarkets-DEMO', 20100321, '@Mahdi.1385', 'US30.U25', 1,
                      datetime.now(timzone).replace(hour=13, minute=30, second=0), timedelta(hours=0))
print(ops.calculate_trade_volume())
ops.start()


# def update_positions(acc_number, acc_password, server):
#     if not mt5.initialize():
#         print("Error initializing MetaTrader 5:", mt5.last_error())
#         quit()
#     if not mt5.login(acc_number, password=acc_password, server=server):
#         print(f"Failed to login: {mt5.last_error()}")
#         mt5.shutdown()
#         quit()
#     while True:
#         time.sleep(0.5)
#         positions = mt5.positions_get()
#         if positions is None or len(positions) == 0:
#             ...
#         else:
#
#             sl_pips = 2000  # مقدار استاپ 1000 پوینت
#
#             for position in positions:
#                 ticket = position.ticket
#                 price_open = position.price_open
#                 symbol = position.symbol
#                 position_type = position.type  # 0: Buy, 1: Sell
#
#                 symbol_info = mt5.symbol_info(symbol)
#                 if not symbol_info:
#                     print(f"خطا در دریافت اطلاعات نماد {symbol}")
#                     continue
#
#                 pip_value = symbol_info.point
#                 if position_type == 0:  # Buy
#                     new_sl = price_open - sl_pips * pip_value
#                 else:  # Sell
#                     new_sl = price_open + sl_pips * pip_value
#
#                 if position.sl != new_sl:
#                     request = {
#                         "action": mt5.TRADE_ACTION_SLTP,
#                         "position": ticket,
#                         "sl": new_sl,
#                         "tp": position.tp
#                     }
#
#                     result = mt5.order_send(request)
#                     if result.retcode == mt5.TRADE_RETCODE_DONE:
#                         print(f"SL برای پوزیشن {ticket} در {symbol} بروزرسانی شد.")
#                     else:
#                         print(f"خطا در بروزرسانی SL برای {symbol}: {result.comment}")
#
#
# update_positions(1054370, 'MmKNpuxDwu@8', 'UNFXB-Real')
