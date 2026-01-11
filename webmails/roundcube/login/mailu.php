<?php

class mailu extends rcube_plugin
{
  public $noajax = true;
  public $noframe = true;

  function init()
  {
    // sso & mailu admin button & password change
    $this->add_hook('startup', array($this, 'startup'));
    // sso
    $this->add_hook('authenticate', array($this, 'authenticate'));
    $this->add_hook('login_after', array($this, 'login'));
    $this->add_hook('login_failed', array($this, 'login_failed'));
    $this->add_hook('logout_after', array($this, 'logout'));
    // mailu admin button and texts
    $this->add_texts('localization/', true);
    
    // password change in settings
    $rcmail = rcmail::get_instance();
    if ($rcmail->task == 'settings' && $rcmail->config->get('show_password_button', true)) {
      $this->add_hook('settings_actions', array($this, 'settings_actions'));
      $this->register_action('plugin.mailu-password', array($this, 'password_form'));
      $this->register_action('plugin.mailu-password-save', array($this, 'password_save'));
    }
  }

  function startup($args)
  {
    $rcmail = rcmail::get_instance();
    if (!$rcmail->output->framed) {
      $this->include_stylesheet($this->local_skin_path() . '/mailu.css');
      
      // mailu admin button - only show for admins
      if ($rcmail->config->get('show_mailu_button', false) && $this->is_admin()) {
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
    }
    // sso
    if (empty($_SESSION['user_id'])) {
      $args['action'] = 'login';
    }
    return $args;
  }
  
  // Check if current user is a global admin
  private function is_admin()
  {
    // Check if we already cached this in the session
    if (isset($_SESSION['mailu_is_admin'])) {
      return $_SESSION['mailu_is_admin'];
    }
    
    $rcmail = rcmail::get_instance();
    $user_email = $rcmail->get_user_name();
    
    if (empty($user_email)) {
      return false;
    }
    
    // Call internal API to check admin status
    $data = json_encode(array('email' => $user_email));
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, 'http://admin:8080/internal/auth/check-admin');
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array('Content-Type: application/json'));
    curl_setopt($ch, CURLOPT_TIMEOUT, 3);
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    $is_admin = false;
    if ($response !== false && $http_code === 200) {
      $result = json_decode($response, true);
      $is_admin = isset($result['is_admin']) ? $result['is_admin'] : false;
    }
    
    // Cache the result in session
    $_SESSION['mailu_is_admin'] = $is_admin;
    
    return $is_admin;
  }
  
  // Add password change to settings menu
  function settings_actions($args)
  {
    $args['actions'][] = array(
      'action' => 'plugin.mailu-password',
      'class'  => 'password',
      'label'  => 'changepassword',
      'title'  => 'changepassword',
      'domain' => 'mailu',
    );
    return $args;
  }
  
  // Display password change form
  function password_form()
  {
    $rcmail = rcmail::get_instance();
    $rcmail->output->set_pagetitle($this->gettext('changepassword'));
    $rcmail->output->add_handlers(array('passwordform' => array($this, 'password_form_html')));
    $rcmail->output->set_env('product_name', $rcmail->config->get('product_name'));
    $rcmail->output->send('mailu.password');
  }
  
  // Generate password form HTML
  function password_form_html($attrib)
  {
    $rcmail = rcmail::get_instance();
    
    $table = new html_table(array('cols' => 2, 'class' => 'propform'));
    
    $field_id = 'curpasswd';
    $input = new html_passwordfield(array(
      'name' => '_curpasswd',
      'id' => $field_id,
      'size' => 30,
      'autocomplete' => 'current-password'
    ));
    $table->add('title', html::label($field_id, rcube::Q($this->gettext('curpasswd'))));
    $table->add(null, $input->show());
    
    $field_id = 'newpasswd';
    $input = new html_passwordfield(array(
      'name' => '_newpasswd',
      'id' => $field_id,
      'size' => 30,
      'autocomplete' => 'new-password'
    ));
    $table->add('title', html::label($field_id, rcube::Q($this->gettext('newpasswd'))));
    $table->add(null, $input->show());
    
    $field_id = 'confpasswd';
    $input = new html_passwordfield(array(
      'name' => '_confpasswd',
      'id' => $field_id,
      'size' => 30,
      'autocomplete' => 'new-password'
    ));
    $table->add('title', html::label($field_id, rcube::Q($this->gettext('confpasswd'))));
    $table->add(null, $input->show());
    
    $form_start = $rcmail->output->form_tag(array(
      'id' => 'password-form',
      'name' => 'password-form',
      'method' => 'post',
      'action' => './?_task=settings&_action=plugin.mailu-password-save'
    ));
    
    $form_end = '</form>';
    
    $submit = html::tag('input', array(
      'type' => 'submit',
      'class' => 'button mainaction submit',
      'value' => $rcmail->gettext('save')
    ));
    
    $cancel = html::tag('button', array(
      'type' => 'button',
      'class' => 'button',
      'onclick' => "location.href='./?_task=mail'; return false;"
    ), $rcmail->gettext('cancel'));
    
    $out = html::div(array('class' => 'box'),
      html::div(array('class' => 'boxtitle'), $this->gettext('changepassword')) .
      html::div(array('class' => 'boxcontent'),
        $form_start .
        $table->show() .
        html::p(array('class' => 'formbuttons footerleft'), $submit . ' ' . $cancel) .
        $form_end
      )
    );
    
    return $out;
  }
  
  // Handle password save
  function password_save()
  {
    $rcmail = rcmail::get_instance();
    
    $curpasswd = rcube_utils::get_input_string('_curpasswd', rcube_utils::INPUT_POST);
    $newpasswd = rcube_utils::get_input_string('_newpasswd', rcube_utils::INPUT_POST);
    $confpasswd = rcube_utils::get_input_string('_confpasswd', rcube_utils::INPUT_POST);
    
    // Validate input
    if (empty($curpasswd)) {
      $rcmail->output->command('display_message', $this->gettext('nocurpassword'), 'error');
      $this->password_form();
      return;
    }
    
    if (empty($newpasswd)) {
      $rcmail->output->command('display_message', $this->gettext('nonewpassword'), 'error');
      $this->password_form();
      return;
    }
    
    if ($newpasswd !== $confpasswd) {
      $rcmail->output->command('display_message', $this->gettext('passwordinconsistency'), 'error');
      $this->password_form();
      return;
    }
    
    if ($curpasswd === $newpasswd) {
      $rcmail->output->command('display_message', $this->gettext('samepasswordfailed'), 'error');
      $this->password_form();
      return;
    }
    
    // Call internal API to change password
    $result = $this->change_password_api($curpasswd, $newpasswd, $confpasswd);
    
    if ($result['success']) {
      // Update the stored password for current session
      $_SESSION['password'] = $rcmail->encrypt($newpasswd);
      $rcmail->output->command('display_message', $this->gettext('successfullysaved'), 'confirmation');
    } else {
      $message = isset($result['message']) ? $result['message'] : $this->gettext('errorsaving');
      $rcmail->output->command('display_message', $message, 'error');
    }
    
    $this->password_form();
  }
  
  // Call internal API for password change
  private function change_password_api($old_password, $new_password, $confirm_password)
  {
    $rcmail = rcmail::get_instance();
    $user_email = $rcmail->get_user_name();
    
    if (empty($user_email)) {
      return array('success' => false, 'message' => 'Not logged in');
    }
    
    $data = json_encode(array(
      'email' => $user_email,
      'old_password' => $old_password,
      'new_password' => $new_password,
      'confirm_password' => $confirm_password
    ));
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, 'http://admin:8080/internal/auth/password');
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
      'Content-Type: application/json'
    ));
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($response === false) {
      return array('success' => false, 'message' => 'Connection failed');
    }
    
    $result = json_decode($response, true);
    if ($result === null) {
      return array('success' => false, 'message' => 'Invalid response');
    }
    
    return $result;
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
