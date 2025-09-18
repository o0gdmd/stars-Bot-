const BASE_URL = "https://stars-bot-fwps.onrender.com"; // ضع هنا رابط السيرفر Flask

async function fetchUserData() {
    const user_id = localStorage.getItem("user_id"); // أو من Telegram WebApp initData
    const res = await fetch(`${BASE_URL}/get_user_data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id })
    });
    const data = await res.json();
    document.getElementById('balance').innerText = data.balance || 0;
}

async function addStars() {
    const amount = parseInt(document.getElementById('addStars').value);
    if(amount < 100) return alert("Minimum 100 Stars");

    const user_id = localStorage.getItem("user_id");
    await fetch(`${BASE_URL}/add_stars`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id, amount })
    });
    alert(`Added ${amount} Stars!`);
    fetchUserData();
}

async function withdrawStars() {
    const amount = parseInt(document.getElementById('withdrawStars').value);
    const user_id = localStorage.getItem("user_id");

    await fetch(`${BASE_URL}/withdraw_stars`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id, amount })
    });
    alert(`Withdraw request sent: ${amount} Stars`);
    fetchUserData();
}

async function updateWallet() {
    const wallet = document.getElementById('wallet').value;
    if(!wallet.startsWith("EQ") && !wallet.startsWith("UQ") && !wallet.endsWith(".ton"))
        return alert("Invalid TON wallet");

    const user_id = localStorage.getItem("user_id");
    await fetch(`${BASE_URL}/update_wallet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id, wallet })
    });
    alert(`Wallet updated to ${wallet}`);
}

fetchUserData();
