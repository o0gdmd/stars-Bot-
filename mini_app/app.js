document.addEventListener('DOMContentLoaded', () => {
    if (Telegram.WebApp) {
        Telegram.WebApp.ready();
        
        // استبدل هذا الرابط برابط تطبيقك على Render
        const API_URL = 'https://stars-bot-fwps.onrender.com/api'; 
        
        // Hide loading and show content
        document.getElementById('loading').style.display = 'none';
        document.getElementById('main-content').style.display = 'block';

        const user = Telegram.WebApp.initDataUnsafe.user;
        const initData = Telegram.WebApp.initData;

        if (user) {
            const username = user.username ? `@${user.username}` : user.first_name;
            document.getElementById('username').textContent = username;
            document.getElementById('userId').textContent = user.id;

            // Fetch the balance from your new API endpoint
            fetch(`${API_URL}/get_balance`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    userId: user.id,
                    user: user, // pass user object
                    initData: initData
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    document.getElementById('balance').textContent = `${data.balance} Stars`;
                    document.getElementById('vipLevel').textContent = data.vip_level;
                    document.getElementById('totalDeposits').textContent = data.total_deposits;
                } else {
                    document.getElementById('balance').textContent = 'Error loading balance.';
                    Telegram.WebApp.showAlert(`Error: ${data.error}`);
                }
            })
            .catch(error => {
                console.error('Error fetching balance:', error);
                document.getElementById('balance').textContent = 'Error.';
                Telegram.WebApp.showAlert('An error occurred. Please try again later.');
            });
        }
    
        // Add Funds Button
        document.getElementById('addFundsBtn').addEventListener('click', () => {
            // This opens the bot's chat and navigates to the 'Add Funds' action
            Telegram.WebApp.openTelegramLink('https://t.me/Tgstarssavebot');
        });

        // Withdraw Button
        document.getElementById('withdrawBtn').addEventListener('click', () => {
            Telegram.WebApp.showPopup({
                title: 'Withdraw Stars',
                message: 'Enter the amount you want to withdraw:',
                buttons: [{ id: 'ok', type: 'ok', text: 'Confirm' }, { id: 'cancel', type: 'cancel', text: 'Cancel' }]
            }, (buttonId) => {
                if (buttonId === 'ok') {
                    const amount = prompt('Enter amount:');
                    if (amount && !isNaN(parseInt(amount))) {
                        // Send the withdrawal request to your new API endpoint
                        fetch(`${API_URL}/request_withdraw`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                userId: user.id,
                                amount: parseInt(amount),
                                user: user, // pass user object
                                initData: initData
                            })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                Telegram.WebApp.showAlert(`✅ ${data.message}`);
                                document.getElementById('balance').textContent = `${data.new_balance} Stars`;
                            } else {
                                Telegram.WebApp.showAlert(`❌ ${data.message}`);
                            }
                        })
                        .catch(error => {
                            console.error('Error during withdrawal:', error);
                            Telegram.WebApp.showAlert('An error occurred. Please try again later.');
                        });
                    }
                }
            });
        });
    }
});
