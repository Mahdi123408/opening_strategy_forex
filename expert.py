import MetaTrader5 as mt5
import time
from datetime import datetime, timedelta
import pytz
import MetaTrader5 as mt5
from datetime import datetime, timedelta


def get_high_low_from_candles(start_time, end_time, symbol, timeframe, timezone):
    from_time = start_time
    to_time = end_time

    # دریافت داده‌های کندل‌ها
    rates = mt5.copy_rates_range(symbol, timeframe, from_time, to_time)

    if rates is None or len(rates) == 0:
        print("No candle data found.")
        return None, None  # در صورت نبود داده

    highest_high = float('-inf')  # مقدار اولیه بیشترین سقف
    lowest_low = float('inf')  # مقدار اولیه کمترین کف

    for rate in rates:
        high = rate['high']
        low = rate['low']
        print(f'high: {high}, low: {low}')
        # به‌روز کردن بیشترین سقف و کمترین کف
        if high > highest_high:
            highest_high = high
        if low < lowest_low:
            lowest_low = low


    return highest_high, lowest_low

def close_all_positions_and_orders(mt5):
    # بستن تمام معاملات باز
    positions = mt5.positions_get()
    if positions:
        for position in positions:
            # دریافت قیمت لحظه‌ای برای نماد
            symbol_info_tick = mt5.symbol_info_tick(position.symbol)
            if not symbol_info_tick:
                print(f"قیمت لحظه‌ای برای نماد {position.symbol} قابل دسترسی نیست.")
                continue

            # تعیین قیمت بر اساس نوع معامله
            price = symbol_info_tick.bid if position.type == mt5.ORDER_TYPE_BUY else symbol_info_tick.ask

            # درخواست بستن معامله
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": price,
                "deviation": 100000000000000,  # مقدار اسلیپیج بالا
            }
            result = mt5.order_send(close_request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"خطا در بستن معامله {position.ticket}: {result.retcode}")
                print(f"جزئیات خطا: {result}")

    # لغو تمام سفارش‌های معلق
    orders = mt5.orders_get()
    if orders:
        for order in orders:
            # درخواست لغو سفارش معلق
            remove_request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": order.ticket,
            }
            result = mt5.order_send(remove_request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"خطا در لغو سفارش {order.ticket}: {result.retcode}")


# ================================
# تابع کمکی جهت بررسی اینکه آیا معامله‌ای با تیک مشخص به سطح TP رسیده است یا خیر
# ================================
def check_trade_tp_hit(ticket, point, timezone):
    # بررسی معاملات بسته‌شده در 5 ساعت گذشته
    from_time = datetime.now(timezone) - timedelta(hours=1)
    to_time = datetime.now(timezone)
    deals = mt5.history_deals_get(from_time.timestamp(), to_time.timestamp())

    if deals is not None:
        b = 0
        while b < len(deals):
            if b >= len(deals) - 1:
                c = b
            else:
                c = b + 1
            if deals[b].order == ticket and deals[c].profit > 0:
                print(f'Trade {ticket} hit TP (Closed Deal).')
                return True
            b += 1

    print(f'Trade {ticket} did not hit TP.')
    return False


# ================================
# توضیحات وضعیت‌ها:
# '0': معامله شروع نشده و بورس آمریکا باز نشده است
# '1': بورس آمریکا باز شده ولی معاملات شروع نشده؛ در این وضعیت دو اوردر اولیه ست می‌شوند
# '2': اوردرهای اولیه ست شده‌اند
# '3': اولین معامله باز شده؛ در این وضعیت اوردر مخالف (اپوزیت) ست می‌شود
# '4': اولین معامله باز است و معامله معکوس ست شده است
# '5': استاپ خوردن معامله اول و باز شدن معامله دوم
# '6': استاپ خوردن معامله دوم و در این مرحله باید اوردرهای معامله آخر ست شوند
# '7': معامله آخر باز شده؛ باید اوردرهای دیگر لغو شده و بررسی شود که آیا معامله به نیمی از تی پی رسیده است
# '8': رسیدن به بیش از نیمی از تی پی معامله آخر؛ باید معامله به حالت ریسک فری (بی‌ضرر) تغییر یابد
# '9': معاملات روز به اتمام رسیده (یا به دلیل رسیدن هر یک از معاملات به TP)
# ================================

status = '0'
# اتصال به متاتریدر
if not mt5.initialize():
    print("Error initializing MetaTrader 5:", mt5.last_error())
    quit()

account = 949851
password = '@Aa123456'
server = 'UNFXB-Real'

# ورود به حساب
if not mt5.login(account, password=password, server=server):
    print(f"Failed to login: {mt5.last_error()}")
    mt5.shutdown()

# نماد داوجونز
symbol = "DJIUSD!"

# منطقه زمانی
timezone = pytz.timezone('UTC')
# متغیرهایی که در مراحل بعد استفاده می‌شوند
lot_size = 0.50
current_time = datetime.now(timezone)
target_time = current_time.replace(hour=14, minute=30, second=0, microsecond=3)
b_opened = False
s_opened = False

while status != '10':
    if status == '0':
        # زمان دقیق باز شدن بورس آمریکا
        current_time = datetime.now(timezone)
        if current_time > target_time:
            status = '1'
            # ادامه روند در وضعیت بعدی
        print(current_time, target_time)
    if status == '1':
        time_5min_before = datetime.now(timezone) - timedelta(minutes=5)
        print(time_5min_before)
        # دریافت داده کندل‌ها از تایم فریم ۵ دقیقه (2 کندل)
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M5, time_5min_before, 1)
        print(mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M5, time_5min_before, 1))
        for rate in rates:
            print(rate)
        if rates is not None and len(rates) > 0:
            # آخرین کندل کامل قبل از باز شدن بازار
            last_candle = rates[0]
            high_last_candle = last_candle['high']
            low_last_candle = last_candle['low']
            # دریافت اطلاعات نماد جهت محاسبه اسپرد و نقطه
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"Symbol {symbol} not found")
                mt5.shutdown()
                quit()
            point = symbol_info.point

            # دریافت اسپرد (نمونه‌ای از میانگین ۳ مقدار اسپرد؛ شما می‌توانید این بخش را تنظیم کنید)
            spread1 = symbol_info.spread
            spread2 = symbol_info.spread
            spread3 = symbol_info.spread
            spread = (spread1 + spread2 + spread3) / 3

            # محاسبه قیمت اوردر بای استاپ و سل استاپ (با افزودن/کاستن 5 پیپ به علاوه اسپرد)
            buy_stop_price = round(high_last_candle + (spread * point) + (500 * point), 2)
            sell_stop_price = round(low_last_candle - (spread * point) - (500 * point), 2)
            first_trade_buy_stop_price = buy_stop_price
            first_trade_sell_stop_price = sell_stop_price
            # تعیین استاپ لاس و تیک پرافیت برای اوردرهای اولیه
            b_stop_loss = round(buy_stop_price - (2000 * point), 2)
            b_take_profit = round(buy_stop_price + (4000 * point), 2)
            s_stop_loss = round(sell_stop_price + (2000 * point), 2)
            s_take_profit = round(sell_stop_price - (4000 * point), 2)

            # ثبت اوردرهای اولیه (Buy Stop و Sell Stop)
            b_request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_BUY_STOP,
                "price": buy_stop_price,
                "sl": b_stop_loss,
                "tp": b_take_profit,
                "type_filling": mt5.ORDER_FILLING_IOC,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            s_request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_SELL_STOP,
                "price": sell_stop_price,
                "sl": s_stop_loss,
                "tp": s_take_profit,
                "type_filling": mt5.ORDER_FILLING_IOC,
                "type_time": mt5.ORDER_TIME_GTC,
            }

            time_5min_before = datetime.now(timezone) - timedelta(minutes=5)
            high_and_low = get_high_low_from_candles(time_5min_before, datetime.now(timezone), symbol, mt5.TIMEFRAME_M5, timezone)


            if high_and_low[0] is not None and high_and_low[1] is not None:
                print(high_and_low)
                if high_and_low[0] > high_last_candle:
                    b_request['price'] = round(high_and_low[0] + (spread * point) + (400 * point), 2)
                    b_request['sl'] = round(b_request['price'] - (2000 * point), 2)
                    b_request['tp'] = round(b_request['price'] + (4000 * point), 2)
                    first_trade_buy_stop_price = b_request['price']


                if high_and_low[1] < low_last_candle:
                    s_request['price'] = round(high_and_low[1] - (spread * point) - (400 * point), 2)
                    s_request['sl'] = round(s_request['price'] + (2000 * point), 2)
                    s_request['tp'] = round(s_request['price'] - (4000 * point), 2)
                    first_trade_sell_stop_price = s_request['price']


            if not b_opened:
                b_result = mt5.order_send(b_request)
            if not  s_opened:
                s_result = mt5.order_send(s_request)


            if b_result.retcode != mt5.TRADE_RETCODE_DONE :
                print(f"Error placing orders: Buy -> {b_result.comment}")
                print(s_request)
            else:
                b_opened = True
                b_order_ticket = b_result.order
                print(f"Buy stop order placed successfully at {buy_stop_price}")


            if s_result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Error placing orders: Sell -> {b_result.comment}")
                print(s_request)
            else:
                s_opened = True
                s_order_ticket = s_result.order
                print(f"Sell stop order placed successfully at {sell_stop_price}")

            if b_opened and s_opened:
                status = '2'
    # وضعیت 2: اوردرهای اولیه ست شده‌اند؛ در این حالت منتظر می‌مانیم تا یکی از اوردرها به پوزیشن تبدیل شود.
    if status == '2':
        print('2')
        while True:
            print('checking trade tp hit...')
            # بررسی اینکه آیا هر یک از اوردرها به TP خورده‌اند
            if check_trade_tp_hit(b_order_ticket, point, timezone) or \
                    check_trade_tp_hit(s_order_ticket, point, timezone):
                print("TP hit on one of the initial orders. Ending trading day.")
                status = '9'
                break

            b_positions = mt5.positions_get(ticket=b_order_ticket)
            s_positions = mt5.positions_get(ticket=s_order_ticket)
            if b_positions is not None and len(b_positions) > 0:
                first_trade = b_positions[0]
                remove_request = {
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": s_order_ticket,
                }
                del_result = mt5.order_send(remove_request)
                print("Canceled pending Sell Stop Order, result:", del_result)
                first_trade_type = 'buy'
                status = '3'
                break
            elif s_positions is not None and len(s_positions) > 0:
                first_trade = s_positions[0]
                remove_request = {
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": b_order_ticket,
                }
                del_result = mt5.order_send(remove_request)
                print("Canceled pending Buy Stop Order, result:", del_result)
                first_trade_type = 'sell'
                status = '3'
                break
            time.sleep(0.5)


    # وضعیت 3: اولین معامله باز شده؛ اکنون اوردر مخالف (اپوزیت) را ست می‌کنیم.
    if status == '3':
        print('3')
        symbol_info = mt5.symbol_info(symbol)
        point = symbol_info.point
        if first_trade_type == 'buy':
            opp_request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_SELL_STOP,
                "price": first_trade.sl,
                "sl": first_trade.sl + (2000 * point),
                "tp": first_trade.sl - (4000 * point),
                "type_filling": mt5.ORDER_FILLING_IOC,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            opp_result = mt5.order_send(opp_request)
            if opp_result.retcode == mt5.TRADE_RETCODE_DONE:
                opposite_order_ticket = opp_result.order
                print("Opposite Sell Stop Order placed, ticket:", opposite_order_ticket)
                status = '4'
            else:
                print("Error placing opposite sell stop order:", opp_result.comment)
        elif first_trade_type == 'sell':
            opp_request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_BUY_STOP,
                "price": first_trade.sl,
                "sl": first_trade.sl - (2000 * point),
                "tp": first_trade.sl + (4000 * point),
                "type_filling": mt5.ORDER_FILLING_IOC,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            opp_result = mt5.order_send(opp_request)
            if opp_result.retcode == mt5.TRADE_RETCODE_DONE:
                opposite_order_ticket = opp_result.order
                print("Opposite Buy Stop Order placed, ticket:", opposite_order_ticket)
                status = '4'
            else:
                print("Error placing opposite buy stop order:", opp_result.comment)

    # وضعیت 4: اولین معامله باز است و معامله اپوزیت ست شده؛ منتظر می‌مانیم تا اولین معامله بسته شود (مثلاً به دلیل SL یا TP)
    if status == '4':
        print('4')
        while True:
            # بررسی اینکه آیا اولین معامله به TP خورده است
            if check_trade_tp_hit(first_trade.ticket, point, timezone):
                print("First trade TP hit. Ending trading day.")
                status = '9'
                break

            first_pos = mt5.positions_get(ticket=first_trade.ticket)
            if first_pos is None or len(first_pos) == 0:
                opp_positions = mt5.positions_get(ticket=opposite_order_ticket)
                if opp_positions is not None and len(opp_positions) > 0:
                    second_trade = opp_positions[0]
                    print("Second trade opened, ticket:", second_trade.ticket)
                    second_trade_ticket = second_trade.ticket
                    status = '5'
                    break
            time.sleep(0.5)

    # وضعیت 5: اولین معامله به استاپ خورده و دومین معامله باز است.
    if status == '5':
        while True:
            # بررسی TP در معامله دوم
            if check_trade_tp_hit(second_trade.ticket, point, timezone):
                print("Second trade TP hit. Ending trading day.")
                status = '9'
                break

            second_pos = mt5.positions_get(ticket=second_trade.ticket)
            if second_pos is None or len(second_pos) == 0:
                print("Second trade closed (stop loss hit).")
                status = '6'
                break
            time.sleep(0.5)


    # وضعیت 6: استاپ خوردن معامله دوم؛ اکنون اوردرهای معامله آخر ست می‌شوند.
    if status == '6':
        current_time = datetime.now(timezone)
        target_time = current_time.replace(hour=14, minute=25, second=0, microsecond=0)
        time_difference = current_time - target_time  # فاصله زمانی
        num_candles = time_difference.total_seconds() / 300 - int(time_difference.total_seconds() / 300)
        if num_candles > 0:
            num_candles = int(time_difference.total_seconds() / 300) + 1
        else:
            num_candles = int(time_difference.total_seconds() / 300)

        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M5, current_time, num_candles)
        if rates is not None:
            high_last_candle = first_trade_buy_stop_price
            low_last_candle = first_trade_sell_stop_price
            print(len(rates))
            for rate in rates:
                print(rate['low'], '-->', rate['high'])
                if rate['high'] > high_last_candle:
                    high_last_candle = rate['high']
                if rate['low'] < low_last_candle:
                    low_last_candle = rate['low']
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"Symbol {symbol} not found")
            point = symbol_info.point

            # دریافت اسپرد (نمونه‌ای از میانگین ۳ مقدار اسپرد؛ شما می‌توانید این بخش را تنظیم کنید)
            spread1 = symbol_info.spread
            spread2 = symbol_info.spread
            spread3 = symbol_info.spread
            spread = (spread1 + spread2 + spread3) / 3

            # محاسبه قیمت اوردر بای استاپ و سل استاپ (با افزودن/کاستن 5 پیپ به علاوه اسپرد)
            buy_stop_price = round(high_last_candle + (spread * point) + (600 * point), 2)
            sell_stop_price = round(low_last_candle - (spread * point) - (500 * point), 2)

            # تعیین استاپ لاس و تیک پرافیت برای اوردرهای اولیه
            b_stop_loss = round(buy_stop_price - (2000 * point), 2)
            b_take_profit = round(buy_stop_price + (6000 * point), 2)
            s_stop_loss = round(sell_stop_price + (2000 * point), 2)
            s_take_profit = round(sell_stop_price - (6000 * point), 2)
            last_b_request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_BUY_STOP,
                "price": buy_stop_price,
                "sl": b_stop_loss,
                "tp": b_take_profit,
                "type_filling": mt5.ORDER_FILLING_IOC,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            last_s_request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_SELL_STOP,
                "price": sell_stop_price,
                "sl": s_stop_loss,
                "tp": s_take_profit,
                "type_filling": mt5.ORDER_FILLING_IOC,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            last_b_result = mt5.order_send(last_b_request)
            print(mt5.last_error())
            last_s_result = mt5.order_send(last_s_request)
            print(mt5.last_error())
            if (last_b_result.retcode == mt5.TRADE_RETCODE_DONE) and (last_s_result.retcode == mt5.TRADE_RETCODE_DONE):
                last_b_order_ticket = last_b_result.order
                last_s_order_ticket = last_s_result.order
                print("Last trade orders placed:", last_b_order_ticket, last_s_order_ticket)
                status = '7'
            else:
                print("Error placing last trade orders.")
                print(mt5.last_error())
        else:
            print("Error placing last trade orders.")
    # وضعیت 7: معامله آخر باز شده؛ ابتدا اوردر معکوس لغو می‌شود و سپس معامله نظارت می‌شود.
    if status == '7':
        while True:
            # بررسی اینکه آیا معامله آخر به TP خورده است
            if check_trade_tp_hit(last_b_order_ticket, point, timezone) or \
                    check_trade_tp_hit(last_s_order_ticket, point, timezone):
                print("Last trade TP hit before opening. Ending trading day.")
                status = '9'
                break

            last_b_positions = mt5.positions_get(ticket=last_b_order_ticket)
            last_s_positions = mt5.positions_get(ticket=last_s_order_ticket)
            if last_b_positions is not None and len(last_b_positions) > 0:
                last_trade = last_b_positions[0]
                remove_request = {
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": last_s_order_ticket,
                }
                del_result = mt5.order_send(remove_request)
                print("Last trade opened as Buy. Canceled pending Sell order.")
                break
            elif last_s_positions is not None and len(last_s_positions) > 0:
                last_trade = last_s_positions[0]
                remove_request = {
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": last_b_order_ticket,
                }
                del_result = mt5.order_send(remove_request)
                print("Last trade opened as Sell. Canceled pending Buy order.")
                break
            time.sleep(0.5)


        # نظارت بر معامله آخر برای رسیدن به نیمی از TP (مثلاً 20 پیپ)
        while True:
            # در هر لحظه بررسی می‌کنیم که آیا معامله به TP خورده است
            if check_trade_tp_hit(last_trade.ticket, point, timezone):
                print("Last trade TP hit. Ending trading day.")
                status = '9'
                break

            current_tick = mt5.symbol_info_tick(symbol)
            if last_trade.type == mt5.POSITION_TYPE_BUY:
                profit_pips = (current_tick.bid - last_trade.price_open) / point
                print(profit_pips)
                print(last_trade.ticket)
                last_pos = mt5.positions_get(ticket=last_trade.ticket)
                print(last_pos)
                if last_pos is None:
                    print("last_pos closed (stop loss hit).")
                    status = '9'
                    break
            else:
                profit_pips = (last_trade.price_open - current_tick.ask) / point
                print(profit_pips)
                print(last_trade.ticket)
                last_pos = mt5.positions_get(ticket=last_trade.ticket)
                print(last_pos)
                if last_pos is None:
                    print("last_pos closed (stop loss hit).")
                    status = '9'
                    break
            if profit_pips >= 5000:
                print("Last trade reached half of TP. Moving to state 8.")
                status = '8'
                break
            time.sleep(0.4)


    # وضعیت 8: رسیدن به بیش از نیمی از TP معامله آخر؛ تغییر استاپ به بی‌ضرر (break even) انجام می‌شود.
    if status == '8':
        # قبل از تغییر استاپ، بررسی TP مجدد
        if check_trade_tp_hit(last_trade.ticket, point, timezone):
            print("Last trade TP hit. Ending trading day.")
            status = '9'
        else:
            if last_trade.type == mt5.POSITION_TYPE_BUY:
                new_stop = last_trade.price_open + (point * 5000)
            else:
                new_stop = last_trade.price_open - (point * 5000)
            modify_request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": last_trade.ticket,
                "symbol": symbol,
                "sl": new_stop,
                "tp": last_trade.tp,  # تی پی همانند قبلی
            }
            modify_result = mt5.order_send(modify_request)
            if modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                print("Last trade modified to risk free.")
                status = '9'
            else:
                print("Error modifying last trade:", modify_result.comment)

    if status == '9':
        print('9')
        close_all_positions_and_orders(mt5)
        status = '10'
        break  # خروج از حلقه اصلی

# قطع ارتباط با MetaTrader
mt5.shutdown()
