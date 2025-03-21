# 删除原有脚本
rm -rf t3rn-bot/
rm -rf t3rn-bot.sh

# 执行我的脚本
wget -O t3rn-bot.sh https://raw.githubusercontent.com/erdongxin/t3rn-bot/refs/heads/main/t3rn-bot.sh && sed -i 's/\r//' t3rn-bot.sh && chmod +x t3rn-bot.sh && ./t3rn-bot.sh
