function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

jQuery(document).ready(function(){
    django.jQuery("input[id^='de_ed_']").each(function(){
        django.jQuery(this).on("keyup change", function(){
            let self = django.jQuery(this);
            let initial =  self.attr("initial");
            let name_id = self.attr("id")
            let self_btn = django.jQuery("#" + name_id + "_btn");
            let self_res = django.jQuery("#" + name_id + "_res");
            if(initial != self.val()){
                self_btn.removeAttr("disabled");
                self_btn.show();
                self_res.removeAttr("disabled");
                self_res.show();
            } else {
                self_btn.attr("disabled", true);
                self_btn.hide();
                self_res.attr("disabled", true);
                self_res.hide();
            }
        });
    });
    django.jQuery("button[id^='de_ed_']").each(function(){
        django.jQuery(this).click("keyup change", function(){
            let self = django.jQuery(this);
            let name_id = self.attr("for");
            console.log(name_id);
            let self_input = django.jQuery("#" + name_id);
            console.log(self_input);
            let instance_id =  self_input.attr("instance_id");
            let value_to_set = self_input.val();
            let real_var_name = self_input.attr("real_var_name");
            let dev_id = self_input.attr("dev_id");
            if(self.attr('id').endsWith('_btn')){
                django.jQuery.ajax({
                    url: 'form_data/edit/' + instance_id + "/" + dev_id + "/"+ real_var_name + "/",
                    method: "PUT",
                    contentType: "application/json",
                    headers: {'X-CSRFToken': getCookie('csrftoken')},
                    data: JSON.stringify({
                        value: value_to_set,
                    }),
                    success: function(){
                        self_input.attr('initial', value_to_set);
                        self_input.trigger("change");
                    },
                    error: function(){
                        alert('error');
                    },
            });
            } else if(self.attr('id').endsWith('_res')) {
                self_input.val(self_input.attr('initial'));
                self_input.trigger("change");
            }
        });
    });
});