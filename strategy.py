import time
import pytz
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import threading

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

class OpeningStrategy():
    def __init__(self, server, acc_number, acc_password, symbol, risk_percent, opening_time, time_difference_to_UTC,
                 stop_pip=20):
        self.server = server
        self.acc_number = acc_number
        self.symbol = symbol
        self.risk_percent = risk_percent
        self.opening_time = opening_time
        self.time_difference_to_UTC = time_difference_to_UTC
        self.stop_pip = stop_pip
        self.acc_password = acc_password
        self.status = 0
        self.monitoring = True
        self.b_opened = False
        self.s_opened = False
        if not mt5.initialize():
            print("Error initializing MetaTrader 5:", mt5.last_error())
            quit()
        if not mt5.login(self.acc_number, password=self.acc_password, server=self.server):
            print(f"Failed to login: {mt5.last_error()}")
            mt5.shutdown()
            quit()
        self.timezone = pytz.timezone('UTC')
        self.mt5 = mt5
        threading.Thread(target=self.update_positions).start()

    def calculate_trade_volume(self):

        # دریافت اطلاعات حساب
        account_info = self.mt5.account_info()
        if account_info is None:
            print("اطلاعات حساب دریافت نشد.")
            return None

        account_balance = account_info.balance  # موجودی حساب

        # دریافت اطلاعات نماد
        symbol_info = self.mt5.symbol_info(self.symbol)
        if symbol_info is None:
            print(f"سیمبول {self.symbol} پیدا نشد.")
            return None

        # محاسبه میزان ریسک دلاری
        risk_amount = int(account_balance * (self.risk_percent / 100))
        # محاسبه حجم معامله
        trade_volume = risk_amount / (self.stop_pip * symbol_info.point) * symbol_info.volume_step

        return round(trade_volume / 100, 2) / 5 * 10

    def close_all_positions_and_orders(self, mt5):
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

    def get_high_low_from_candles(self, start_time, end_time, symbol, timeframe):
        from_time = start_time
        to_time = end_time

        # دریافت داده‌های کندل‌ها
        rates = self.mt5.copy_rates_range(symbol, timeframe, from_time, to_time)

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

    def update_positions(self):
        ...
        # while self.monitoring:
        #     time.sleep(0.3)
        #     positions = self.mt5.positions_get()
        #     if positions is None or len(positions) == 0:
        #         ...
        #     else:
        #         if self.status < 6:
        #             tp_pips = 4000  # مقدار تیپی 2000 پوینت
        #             sl_pips = 2000  # مقدار استاپ 1000 پوینت
        #         else:
        #             tp_pips = 6000  # مقدار تیپی 3000 پوینت
        #             sl_pips = 2000  # مقدار استاپ 1000 پوینت
        #
        #         for position in positions:
        #             ticket = position.ticket
        #             price_open = position.price_open
        #             symbol = position.symbol
        #             position_type = position.type  # 0: Buy, 1: Sell
        #
        #             symbol_info = self.mt5.symbol_info(symbol)
        #             if not symbol_info:
        #                 print(f"خطا در دریافت اطلاعات نماد {symbol}")
        #                 continue
        #
        #             pip_value = symbol_info.point
        #             if position_type == 0:  # Buy
        #                 new_sl = price_open - sl_pips * pip_value
        #                 new_tp = price_open + tp_pips * pip_value
        #             else:  # Sell
        #                 new_sl = price_open + sl_pips * pip_value
        #                 new_tp = price_open - tp_pips * pip_value
        #
        #             if position.sl != new_sl or position.tp != new_tp:
        #                 request = {
        #                     "action": mt5.TRADE_ACTION_SLTP,
        #                     "position": ticket,
        #                     "sl": new_sl,
        #                     "tp": new_tp
        #                 }
        #
        #                 result = self.mt5.order_send(request)
        #                 if result.retcode == self.mt5.TRADE_RETCODE_DONE:
        #                     print(f"SL/TP برای پوزیشن {ticket} در {symbol} بروزرسانی شد.")
        #                 else:
        #                     print(f"خطا در بروزرسانی SL/TP برای {symbol}: {result.comment}")

    def start(self):
        try:
            while self.status == 0:
                # زمان دقیق باز شدن بورس آمریکا
                current_time = datetime.now(self.timezone) + self.time_difference_to_UTC
                if current_time > self.opening_time:
                    self.status = 1
                    self.status_1()
                    print('end .')
                    # ادامه روند در وضعیت بعدی
        except Exception as e:
            print(f"یک خطا در استاتوس 0 رخ داد: \n{e}")

    def check_trade_tp_hit(self, ticket):
        from_time = datetime.now(self.timezone) - timedelta(hours=5) + self.time_difference_to_UTC
        to_time = datetime.now(self.timezone) + self.time_difference_to_UTC
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
        return False

    def status_1(self):
        try:
            while self.status == 1:
                time_5min_before = datetime.now(self.timezone) - timedelta(minutes=5) + self.time_difference_to_UTC
                rates = self.mt5.copy_rates_from(self.symbol, self.mt5.TIMEFRAME_M5, time_5min_before, 1)

                if rates is not None and len(rates) > 0:
                    # آخرین کندل کامل قبل از باز شدن بازار
                    last_candle = rates[0]
                    high_last_candle = last_candle['high']
                    low_last_candle = last_candle['low']
                    # دریافت اطلاعات نماد جهت محاسبه اسپرد و نقطه
                    symbol_info = self.mt5.symbol_info(self.symbol)
                    if symbol_info is None:
                        print(f"Symbol {self.symbol} not found")
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
                    self.first_trade_buy_stop_price = buy_stop_price
                    self.first_trade_sell_stop_price = sell_stop_price
                    # تعیین استاپ لاس و تیک پرافیت برای اوردرهای اولیه
                    b_stop_loss = round(buy_stop_price - (2000 * point), 2)
                    b_take_profit = round(buy_stop_price + (4000 * point), 2)
                    s_stop_loss = round(sell_stop_price + (2000 * point), 2)
                    s_take_profit = round(sell_stop_price - (4000 * point), 2)

                    # ثبت اوردرهای اولیه (Buy Stop و Sell Stop)
                    b_request = {
                        "action": self.mt5.TRADE_ACTION_PENDING,
                        "symbol": self.symbol,
                        "volume": self.calculate_trade_volume(),
                        "type": self.mt5.ORDER_TYPE_BUY_STOP,
                        "price": buy_stop_price,
                        "sl": b_stop_loss,
                        "tp": b_take_profit,
                        "type_filling": self.mt5.ORDER_FILLING_IOC,
                        "type_time": self.mt5.ORDER_TIME_GTC,
                    }
                    s_request = {
                        "action": self.mt5.TRADE_ACTION_PENDING,
                        "symbol": self.symbol,
                        "volume": self.calculate_trade_volume(),
                        "type": self.mt5.ORDER_TYPE_SELL_STOP,
                        "price": sell_stop_price,
                        "sl": s_stop_loss,
                        "tp": s_take_profit,
                        "type_filling": self.mt5.ORDER_FILLING_IOC,
                        "type_time": self.mt5.ORDER_TIME_GTC,
                    }

                    high_and_low = self.get_high_low_from_candles(time_5min_before,
                                                                  datetime.now(
                                                                      self.timezone) + self.time_difference_to_UTC,
                                                                  self.symbol,
                                                                  self.mt5.TIMEFRAME_M5)

                    if high_and_low[0] is not None and high_and_low[1] is not None:
                        print(high_and_low)
                        if high_and_low[0] > high_last_candle:
                            b_request['price'] = round(high_and_low[0] + (spread * point) + (400 * point), 2)
                            b_request['sl'] = round(b_request['price'] - (2000 * point), 2)
                            b_request['tp'] = round(b_request['price'] + (4000 * point), 2)
                            self.first_trade_buy_stop_price = b_request['price']

                        if high_and_low[1] < low_last_candle:
                            s_request['price'] = round(high_and_low[1] - (spread * point) - (400 * point), 2)
                            s_request['sl'] = round(s_request['price'] + (2000 * point), 2)
                            s_request['tp'] = round(s_request['price'] - (4000 * point), 2)
                            self.first_trade_sell_stop_price = s_request['price']

                    if not self.b_opened:
                        b_result = self.mt5.order_send(b_request)
                    if not self.s_opened:
                        s_result = self.mt5.order_send(s_request)

                    if b_result.retcode != self.mt5.TRADE_RETCODE_DONE:
                        print(f"Error placing orders: Buy -> {b_result.comment}")
                        print(s_request)
                    else:
                        self.b_opened = True
                        self.b_order_ticket = b_result.order
                        print(f"Buy stop order placed successfully at {buy_stop_price}")

                    if s_result.retcode != mt5.TRADE_RETCODE_DONE:
                        print(f"Error placing orders: Sell -> {b_result.comment}")
                        print(s_request)
                    else:
                        self.s_opened = True
                        self.s_order_ticket = s_result.order
                        print(f"Sell stop order placed successfully at {sell_stop_price}")

                    if self.b_opened and self.s_opened:
                        self.status = 2
                        self.status_2()
        except Exception as e:
            print(f"یک خطا در استاتوس 2 رخ داد: \n{e}")

    # وضعیت 2: اوردرهای اولیه ست شده‌اند؛ در این حالت منتظر می‌مانیم تا یکی از اوردرها به پوزیشن تبدیل شود.
    def status_2(self):
        try:
            while self.status == 2:
                if self.check_trade_tp_hit(self.b_order_ticket) or \
                        self.check_trade_tp_hit(self.s_order_ticket):
                    print("TP hit on one of the initial orders. Ending trading day.")
                    self.status = 9
                    self.status_9()
                    break

                self.b_positions = mt5.positions_get(ticket=self.b_order_ticket)
                self.s_positions = mt5.positions_get(ticket=self.s_order_ticket)
                if self.b_positions is not None and len(self.b_positions) > 0:
                    self.first_trade = self.b_positions[0]
                    remove_request = {
                        "action": mt5.TRADE_ACTION_REMOVE,
                        "order": self.s_order_ticket,
                    }
                    del_result = mt5.order_send(remove_request)
                    print("Canceled pending Sell Stop Order, result:", del_result)
                    self.first_trade_type = 'buy'
                    self.status = 3
                    self.status_3()
                    break
                elif self.s_positions is not None and len(self.s_positions) > 0:
                    self.first_trade = self.s_positions[0]
                    remove_request = {
                        "action": mt5.TRADE_ACTION_REMOVE,
                        "order": self.b_order_ticket,
                    }
                    del_result = mt5.order_send(remove_request)
                    print("Canceled pending Buy Stop Order, result:", del_result)
                    self.first_trade_type = 'sell'
                    self.status = 3
                    self.status_3()
                    break
                time.sleep(0.5)
        except Exception as e:
            print(f"یک خطا در استاتوس 2 رخ داد: \n{e}")

    # وضعیت 3: اولین معامله باز شده؛ اکنون اوردر مخالف (اپوزیت) را ست می‌کنیم.
    def status_3(self):
        try:
            while self.status == 3:
                symbol_info = mt5.symbol_info(self.symbol)
                point = symbol_info.point
                if self.first_trade_type == 'buy':
                    opp_request = {
                        "action": mt5.TRADE_ACTION_PENDING,
                        "symbol": self.symbol,
                        "volume": self.calculate_trade_volume(),
                        "type": mt5.ORDER_TYPE_SELL_STOP,
                        "price": self.first_trade.sl,
                        "sl": self.first_trade.sl + (2000 * point),
                        "tp": self.first_trade.sl - (4000 * point),
                        "type_filling": mt5.ORDER_FILLING_IOC,
                        "type_time": mt5.ORDER_TIME_GTC,
                    }
                    opp_result = mt5.order_send(opp_request)
                    if opp_result.retcode == mt5.TRADE_RETCODE_DONE:
                        self.opposite_order_ticket = opp_result.order
                        print("Opposite Sell Stop Order placed, ticket:", self.opposite_order_ticket)
                        self.status = 4
                        self.status_4()
                    else:
                        print("Error placing opposite sell stop order:", opp_result.comment)
                elif self.first_trade_type == 'sell':
                    opp_request = {
                        "action": mt5.TRADE_ACTION_PENDING,
                        "symbol": self.symbol,
                        "volume": self.calculate_trade_volume(),
                        "type": mt5.ORDER_TYPE_BUY_STOP,
                        "price": self.first_trade.sl,
                        "sl": self.first_trade.sl - (2000 * point),
                        "tp": self.first_trade.sl + (4000 * point),
                        "type_filling": mt5.ORDER_FILLING_IOC,
                        "type_time": mt5.ORDER_TIME_GTC,
                    }
                    opp_result = mt5.order_send(opp_request)
                    if opp_result.retcode == mt5.TRADE_RETCODE_DONE:
                        self.opposite_order_ticket = opp_result.order
                        print("Opposite Buy Stop Order placed, ticket:", self.opposite_order_ticket)
                        self.status = 4
                        self.status_4()
                    else:
                        print("Error placing opposite buy stop order:", opp_result.comment)

        except Exception as e:
            print(f"یک خطا در استاتوس 3 رخ داد: \n{e}")

    # وضعیت 4: اولین معامله باز است و معامله اپوزیت ست شده؛ منتظر می‌مانیم تا اولین معامله بسته شود (مثلاً به دلیل SL یا TP)
    def status_4(self):
        try:
            while self.status == 4:
                if self.check_trade_tp_hit(self.first_trade.ticket):
                    print("First trade TP hit. Ending trading day.")
                    self.status = 9
                    self.status_9()
                    break

                self.first_pos = mt5.positions_get(ticket=self.first_trade.ticket)
                if self.first_pos is None or len(self.first_pos) == 0:
                    self.opp_positions = mt5.positions_get(ticket=self.opposite_order_ticket)
                    if self.opp_positions is not None and len(self.opp_positions) > 0:
                        self.second_trade = self.opp_positions[0]
                        print("Second trade opened, ticket:", self.second_trade.ticket)
                        self.second_trade_ticket = self.second_trade.ticket
                        self.status = 5
                        self.status_5()
                        break
                time.sleep(0.5)
        except Exception as e:
            print(f"یک خطا در استاتوس 4 رخ داد: \n{e}")

    # وضعیت 5: اولین معامله به استاپ خورده و دومین معامله باز است.
    def status_5(self):
        try:
            while self.status == 5:
                if self.check_trade_tp_hit(self.second_trade.ticket):
                    print("Second trade TP hit. Ending trading day.")
                    self.status = 9
                    self.status_9()
                    break

                self.second_pos = mt5.positions_get(ticket=self.second_trade.ticket)
                if self.second_pos is None or len(self.second_pos) == 0:
                    print("Second trade closed (stop loss hit).")
                    self.status = 6
                    self.status_6()
                    break
                time.sleep(0.5)
        except Exception as e:
            print(f"یک خطا در استاتوس 5 رخ داد: \n{e}")

    # وضعیت 6: استاپ خوردن معامله دوم؛ اکنون اوردرهای معامله آخر ست می‌شوند.
    def status_6(self):
        try:
            while self.status == 6:
                current_time = datetime.now(self.timezone)
                target_time = self.opening_time - timedelta(minutes=5)
                time_difference = current_time - target_time  # فاصله زمانی
                num_candles = time_difference.total_seconds() / 300 - int(time_difference.total_seconds() / 300)
                if num_candles > 0:
                    num_candles = int(time_difference.total_seconds() / 300) + 1
                else:
                    num_candles = int(time_difference.total_seconds() / 300)

                rates = mt5.copy_rates_from(self.symbol, mt5.TIMEFRAME_M5, current_time, num_candles)
                if rates is not None:
                    high_last_candle = self.first_trade_buy_stop_price
                    low_last_candle = self.first_trade_sell_stop_price
                    for rate in rates:
                        if rate['high'] > high_last_candle:
                            high_last_candle = rate['high']
                        if rate['low'] < low_last_candle:
                            low_last_candle = rate['low']
                    symbol_info = mt5.symbol_info(self.symbol)
                    if symbol_info is None:
                        print(f"Symbol {self.symbol} not found")
                    point = symbol_info.point

                    spread1 = symbol_info.spread
                    spread2 = symbol_info.spread
                    spread3 = symbol_info.spread
                    spread = (spread1 + spread2 + spread3) / 3

                    buy_stop_price = round(high_last_candle + (spread * point) + (600 * point), 2)
                    sell_stop_price = round(low_last_candle - (spread * point) - (500 * point), 2)

                    b_stop_loss = round(buy_stop_price - (2000 * point), 2)
                    b_take_profit = round(buy_stop_price + (6000 * point), 2)
                    s_stop_loss = round(sell_stop_price + (2000 * point), 2)
                    s_take_profit = round(sell_stop_price - (6000 * point), 2)
                    last_b_request = {
                        "action": mt5.TRADE_ACTION_PENDING,
                        "symbol": self.symbol,
                        "volume": self.calculate_trade_volume(),
                        "type": mt5.ORDER_TYPE_BUY_STOP,
                        "price": buy_stop_price,
                        "sl": b_stop_loss,
                        "tp": b_take_profit,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                        "type_time": mt5.ORDER_TIME_GTC,
                    }
                    last_s_request = {
                        "action": mt5.TRADE_ACTION_PENDING,
                        "symbol": self.symbol,
                        "volume": self.calculate_trade_volume(),
                        "type": mt5.ORDER_TYPE_SELL_STOP,
                        "price": sell_stop_price,
                        "sl": s_stop_loss,
                        "tp": s_take_profit,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                        "type_time": mt5.ORDER_TIME_GTC,
                    }
                    self.last_b_result = mt5.order_send(last_b_request)
                    print(mt5.last_error())
                    self.last_s_result = mt5.order_send(last_s_request)
                    print(mt5.last_error())
                    if (self.last_b_result.retcode == mt5.TRADE_RETCODE_DONE) and (
                            self.last_s_result.retcode == mt5.TRADE_RETCODE_DONE):
                        self.last_b_order_ticket = self.last_b_result.order
                        self.last_s_order_ticket = self.last_s_result.order
                        print("Last trade orders placed:", self.last_b_order_ticket, self.last_s_order_ticket)
                        self.status = 7
                        self.status_7()
                    else:
                        print("Error placing last trade orders.")
                        print(mt5.last_error())
                else:
                    print("Error placing last trade orders.")
        except Exception as e:
            print(f"یک خطا در استاتوس 6 رخ داد: \n{e}")

    # وضعیت 7: معامله آخر باز شده؛ ابتدا اوردر معکوس لغو می‌شود و سپس معامله نظارت می‌شود.
    def status_7(self):
        try:
            while self.status == 7:
                ...
        except Exception as e:
            print(f"یک خطا در استاتوس 7 رخ داد: \n{e}")

    # وضعیت 8: رسیدن به بیش از نیمی از TP معامله آخر؛ تغییر استاپ به بی‌ضرر (break even) انجام می‌شود.
    def status_8(self):
        try:
            while self.status == 8:
                ...
        except Exception as e:
            print(f"یک خطا در استاتوس 8 رخ داد: \n{e}")


    def status_9(self):
        try:
            self.close_all_positions_and_orders(mt5)
            quit()
        except Exception as e:
            print(f"یک خطا در استاتوس 9 رخ داد: \n{e}")
