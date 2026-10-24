<?php

class mailu extends rcube_plugin
{
  public $noajax = true;

  function init()
  {
    // sso & mailu admin button
    $this->add_hook('startup', array($this, 'startup'));
    // sso
    $this->add_hook('authenticate', array($this, 'authenticate'));
    $this->add_hook('login_after', array($this, 'login'));
    $this->add_hook('login_failed', array($this, 'login_failed'));
    $this->add_hook('logout_after', array($this, 'logout'));
    // mailu admin button
    $this->add_texts('localization/', false);
  }

  function startup($args)
  {
    // mailu admin button
    $rcmail = rcmail::get_instance();
    if (!$rcmail->output->framed and $rcmail->config->get('show_mailu_button', false)) {
      $this->include_stylesheet($this->local_skin_path() . '/mailu.css');
      $this->add_button([
          'type'       => 'link',
          'href'       => $rcmail->config->get('support_url'),
          'class'      => 'button-mailu',
          'label'      => 'mailu.mailu',
          'tabindex'   => '0',
          'innerclass' => 'button-inner',
        ], 'taskbar'
      );
    }
    // sso
    if (empty($_SESSION['user_id'])) {
      $args['action'] = 'login';
    }
    return $args;
  }

  function authenticate($args)
  {
    if (!array_key_exists('HTTP_X_REMOTE_USER', $_SERVER) or !array_key_exists('HTTP_X_REMOTE_USER_TOKEN', $_SERVER)) {
      if ($_SERVER['PHP_SELF'] == '/sso.php') {
        http_response_code(403);
        print('mailu sso failure');
      } else {
        header('Location: sso.php', true, 302);
      }
      exit();
    }

    $args['user'] = $_SERVER['HTTP_X_REMOTE_USER'];
    $args['pass'] = $_SERVER['HTTP_X_REMOTE_USER_TOKEN'];

    $args['cookiecheck'] = false;
    $args['valid'] = true;

    return $args;
  }

  // Redirect to global SSO logout path.
  function logout($args)
  {
    $this->load_config();
    $sso_logout_url = rcmail::get_instance()->config->get('sso_logout_url');
    header('Location: ' . $sso_logout_url, true, 302);
    exit();
  }

  function login($args)
  {
    $this->sync_identities();
    header('Location: index.php', true, 302);
    exit();
  }

  /**
   * Keep Mailu-managed sender aliases in sync after a successful SSO login.
   * User-created identities are left alone; only identities recorded in the
   * user's Roundcube preferences are removed when Mailu no longer provides
   * the corresponding alias.
   */
  private function sync_identities()
  {
    if (($_SERVER['HTTP_X_REMOTE_USER_ALIASES_COMPLETE'] ?? '') !== 'true') {
      return;
    }

    $rcmail = rcmail::get_instance();
    $aliases = [];
    foreach (explode(',', $_SERVER['HTTP_X_REMOTE_USER_ALIASES'] ?? '') as $email) {
      if (!$email || strpos($email, '@') === false) {
        continue;
      }
      $email = strtolower(rcube_utils::idn_to_ascii($email));
      $aliases[$email] = true;
    }

    $prefs = $rcmail->user->get_prefs();
    $previously_managed = $prefs['mailu_alias_identities'] ?? [];
    if (!is_array($previously_managed)) {
      $previously_managed = [];
    }
    $previously_managed = array_filter($previously_managed, 'is_string');
    $previously_managed = array_fill_keys(array_map('strtolower', $previously_managed), true);

    $identities = $rcmail->user->list_identities();
    $identities_by_email = [];
    foreach ($identities as $identity) {
      $email = strtolower(rcube_utils::idn_to_ascii($identity['email']));
      $identities_by_email[$email] = $identity;
    }

    $managed = [];

    foreach ($previously_managed as $email => $_) {
      if (isset($aliases[$email])) {
        if (isset($identities_by_email[$email])) {
          $managed[$email] = true;
        }
        continue;
      }

      if (!isset($identities_by_email[$email])) {
        continue;
      }
      $identity = $identities_by_email[$email];
      if (!empty($identity['standard']) || $rcmail->user->delete_identity($identity['identity_id']) !== true) {
        $managed[$email] = true;
      }
      unset($identities_by_email[$email]);
    }

    $default_identity = $rcmail->user->get_identity();
    foreach ($aliases as $email => $_) {
      if (isset($identities_by_email[$email])) {
        // Do not claim or later delete identities that the user created.
        continue;
      }

      $record = [
        'user_id' => $rcmail->user->ID,
        'standard' => 0,
        'name' => $default_identity['name'] ?? '',
        'email' => $email,
        'organization' => $default_identity['organization'] ?? '',
        'reply-to' => '',
        'bcc' => '',
        'signature' => $default_identity['signature'] ?? '',
        'html_signature' => $default_identity['html_signature'] ?? 0,
      ];
      $plugin = $rcmail->plugins->exec_hook('identity_create', [
        'login' => true,
        'record' => $record,
      ]);

      if (!empty($plugin['abort']) || empty($plugin['record']['email'])
          || !$rcmail->user->insert_identity($plugin['record'])) {
        continue;
      }
      $managed[strtolower(rcube_utils::idn_to_ascii($plugin['record']['email']))] = true;
    }

    $rcmail->user->save_prefs([
      'mailu_alias_identities' => array_keys($managed),
    ]);
  }

  function login_failed($args)
  {
    header('Location: sso.php', true, 302);
    exit();
  }

}
