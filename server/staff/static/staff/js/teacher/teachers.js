/**
 * Created by liumengjun on 1/12/16.
 */

$(function(){
    $('[data-action=donot-choose]').click(function(e){
        $row = $(this).closest('tr');
        teacherId = $row.attr('teacherId');
        alert("这个老师不行吗?"+teacherId);
        params = {'action': "donot-choose", 'teacherId': teacherId};
        $.post( "/staff/teachers/action/", function( result ) {
            alert(JSON.stringify(result));
        }, 'json').fail(function() {
            alert( "请求失败,请稍后重试,或联系管理员!" );
        });
    });
    $('[data-action=invite-interview]').click(function(e){
        alert("你邀请了这个老师");
    });
    $('[data-action=set-interview-ok]').click(function(e){
        alert("欢迎这位老师的加入");
    });
    $('[data-action=set-interview-fail]').click(function(e){
        alert("哎哟,这个老师被pass掉了");
    });
});
