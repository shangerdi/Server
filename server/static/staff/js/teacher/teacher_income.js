/**
 * Created by liumengjun on 2/25/16.
 */

$(function() {
    var defaultErrMsg = '请求失败,请稍后重试,或联系管理员!';

    $('form[name=query_form]').on('submit', function (e) {
        var dateFrom = $('input[name=date_from]').val(), dateTo = $('input[name=date_to]').val();
        if (dateFrom && dateTo && dateFrom>dateTo) {
            alert("请确保截止查询日期大于等于开始日期");
            return false;
        }
        var phone = $.trim($(this).find('input[name=phone]').val());
        if (phone && (!/^\d+$/.test(phone) || phone.length > 11)) {
            alert('手机号格式错误');
            return false;
        }
        return true;
    });

    $('[data-action="export-excel"]').click(function(e){
        var $form = $(this).closest('form');
        var params_str = $form.serialize();
        window.open(location.pathname+"?export=true&"+params_str);
    });

    paginationInit();
});
