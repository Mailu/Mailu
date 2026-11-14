(() => {
	const accountSettingsUrl = window.rl?.pluginSettingsGet('mailu-identities', 'accountSettingsUrl')
		|| new URL('../../admin/user/settings', window.location.href).href;

	const addAccountSettingsLink = () => {
		const menu = document.querySelector('#top-system-dropdown-id + menu');
		if (!menu || menu.querySelector('.mailu-account-settings')) {
			return;
		}

		const divider = document.createElement('li');
		divider.className = 'dividerbar';
		divider.setAttribute('role', 'presentation');

		const item = document.createElement('li');
		item.setAttribute('role', 'presentation');

		const link = document.createElement('a');
		link.className = 'mailu-account-settings';
		link.href = accountSettingsUrl;
		link.tabIndex = -1;
		link.dataset.icon = '⚙';
		link.textContent = 'Mailu account management';
		item.append(link);

		const logout = menu.querySelector('a[data-bind*="logoutClick"]')?.closest('li');
		if (logout) {
			menu.insertBefore(divider, logout);
			menu.insertBefore(item, logout);
		} else {
			menu.append(divider, item);
		}
	};

	new MutationObserver(addAccountSettingsLink).observe(document.documentElement, {
		childList: true,
		subtree: true
	});
	addAccountSettingsLink();
})();
