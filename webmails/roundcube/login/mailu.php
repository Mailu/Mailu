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
    if (empty($_SESSION['username']) || (!empty($_SERVER['HTTP_X_REMOTE_USER']) && $_SESSION['username'] !== $_SERVER['HTTP_X_REMOTE_USER'])) {
      $args['task'] = 'login';
      $args['action'] = 'login';
    }

    if (!$rcmail->output->framed && !empty($_SESSION['mailu_original_username']) && $_SESSION['mailu_original_username'] !== $_SESSION['username']) {
      $currentUser = $_SESSION['username'];
      $originalUser = $_SESSION['mailu_original_username'];

      $link = html::a(
        sprintf('%s/user/webmail', $rcmail->config->get('support_url')),
        $this->gettext([
          'name' => 'impersonationwarninglink',
          'vars' => [
            'email' => html::quote($originalUser),
          ],
        ]),
      );

      $this->api->output->add_header(html::tag(
        'div',
        'boxwarning',
        $this->gettext([
          'name' => 'impersonationwarning',
          'vars' => [
            'email' => html::quote($currentUser),
            'link' => $link,
          ],
        ]),
      ));
    }

    return $args;
  }

  function authenticate($args)
  {
    if (!array_key_exists('HTTP_X_REMOTE_USER', $_SERVER) or !array_key_exists('HTTP_X_REMOTE_USER_TOKEN', $_SERVER)) {
      if ($_SERVER['PHP_SELF'] == '/sso.php') {
        header('HTTP/1.0 403 Forbidden');
        print('mailu sso failure');
      } else {
        header('Location: sso.php', 302);
      }
      exit();
    }

    $args['user'] = $_SERVER['HTTP_X_REMOTE_USER'];
    $args['pass'] = $_SERVER['HTTP_X_REMOTE_USER_TOKEN'];

    $_SESSION['mailu_original_username'] = $_SERVER['HTTP_X_REMOTE_ORIGINAL_USER'];

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
    header('Location: index.php', 302);
    exit();
  }

  function login_failed($args)
  {
    header('Location: sso.php', 302);
    exit();
  }

}
