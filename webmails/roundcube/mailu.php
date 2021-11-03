<?php

class mailu extends rcube_plugin
{

  function init()
  {
    $this->add_hook('startup', array($this, 'startup'));
    $this->add_hook('authenticate', array($this, 'authenticate'));
    $this->add_hook('login_after', array($this, 'login'));
    $this->add_hook('login_failed', array($this, 'login_failed'));
    $this->add_hook('logout_after', array($this, 'logout'));
  }

  function startup($args)
  {
    if (empty($_SESSION['user_id'])) {
        $args['action'] = 'login';
    }

    return $args;
  }

  function authenticate($args)
  {
    if (!array_key_exists('HTTP_X_REMOTE_USER', $_SERVER) or !array_key_exists('HTTP_X_REMOTE_USER_TOKEN', $_SERVER)) {
        header('Location: sso.php');
        exit();
    }
    $args['user'] = $_SERVER['HTTP_X_REMOTE_USER'];
    $args['pass'] = $_SERVER['HTTP_X_REMOTE_USER_TOKEN'];

    $args['cookiecheck'] = false;
    $args['valid'] = true;

    return $args;
  }

  function logout($args) {
    // Redirect to global SSO logout path.
    $this->load_config();

    $sso_logout_url = rcmail::get_instance()->config->get('sso_logout_url');
    header("Location: " . $sso_logout_url, true);
    exit;
  }

  function login($args)
  {
      header('Location: index.php');
      exit();
  }
  function login_failed($args)
  {
      $ua = $_SERVER['HTTP_USER_AGENT'];
      $ra = $_SERVER['REMOTE_ADDR'];
      if ($ua == 'health' and ($ra == '127.0.0.1' or $ra == '::1')) {
        echo "OK";
        exit;
      }
      header('Location: sso.php');
      exit();
  }

}
