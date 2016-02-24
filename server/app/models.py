import datetime

import posix_ipc
from segmenttree import SegmentTree

from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth import authenticate
from django.apps import apps
from django.utils import timezone

from app.exception import TimeSlotConflict
from app.utils.algorithm import orderid, Tree, Node
from app.utils import random_string, classproperty
from django.utils.timezone import make_aware


class BaseModel(models.Model):
    class Meta:
        abstract = True


class Policy(BaseModel):
    content = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)


class Region(BaseModel):
    """
    Province, City & District
    """
    name = models.CharField(max_length=50)
    superset = models.ForeignKey('Region', blank=True, null=True, default=None,
                                 on_delete=models.SET_NULL)
    admin_level = models.PositiveIntegerField()
    leaf = models.BooleanField()
    weekly_time_slots = models.ManyToManyField('WeeklyTimeSlot')
    opened = models.BooleanField(default=False)

    def __str__(self):
        return '%s (%d)' % (self.name, self.admin_level)

    def full_name(self, sep='-'):
        full_name = self.name
        upper = self.superset
        while upper:
            full_name = upper.name + sep + full_name
            upper = upper.superset
        return full_name

    def make_dict(self):
        _dict = {}
        _region = self
        while _region:
            if _region.admin_level == 1:
                _dict['province'] = _region
            elif _region.admin_level == 2:
                _dict['city'] = _region
            elif _region.admin_level == 3:
                _dict['district'] = _region
            _region = _region.superset
        return _dict


class Memberservice(BaseModel):
    name = models.CharField(max_length=30, unique=True)
    detail = models.CharField(max_length=1000)

    def __str__(self):
        return '%s' % self.name


class School(BaseModel):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    thumbnail = models.ImageField(upload_to='schools', null=True, blank=True)
    region = models.ForeignKey(Region, limit_choices_to={'opened': True})
    center = models.BooleanField()
    longitude = models.IntegerField()
    latitude = models.IntegerField()
    opened = models.BooleanField(default=False)
    class_seat = models.IntegerField(default=0, null=True)
    study_seat = models.IntegerField(default=0, null=True)
    phone = models.CharField(max_length=20, default=None, null=True)
    member_services = models.ManyToManyField(Memberservice)

    def __str__(self):
        return '%s%s %s' % (self.region, self.name, 'C' if self.center else '')


class SchoolPhoto(BaseModel):
    school = models.ForeignKey(School)
    img = models.ImageField(null=True, blank=True, upload_to='schools')

    def __str__(self):
        return self.school

    def img_url(self):
        return self.img and self.img.url or ''


class Subject(BaseModel):
    ENGLISH = None
    name = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_english(cls):
        if not cls.ENGLISH:
            cls.ENGLISH = Subject.objects.get(name='英语')
        return cls.ENGLISH


class Tag(BaseModel):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


class Grade(BaseModel):
    name = models.CharField(max_length=10, unique=True)
    superset = models.ForeignKey('Grade', blank=True, null=True, default=None,
                                 on_delete=models.SET_NULL,
                                 related_name='subset')
    leaf = models.BooleanField()

    def __str__(self):
        return self.name

    @property
    def subjects(self):
        Ability = apps.get_model('app', 'Ability')
        ans = Ability.objects.filter(grade=self)
        for one in ans:
            yield one.subject

    @staticmethod
    def get_all_grades():
        """
        获得所有的grade名称
        """
        return [[item.name for item in item.subset.all()]
                for item in Grade.objects.filter(superset=None)]


class Ability(BaseModel):
    grade = models.ForeignKey(Grade)
    subject = models.ForeignKey(Subject)

    class Meta:
        unique_together = ('grade', 'subject')

    def __str__(self):
        return '%s, %s' % (self.grade, self.subject)


class Level(BaseModel):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


class Price(BaseModel):
    region = models.ForeignKey(Region, limit_choices_to={'opened': True})
    ability = models.ForeignKey(Ability, default=1)
    level = models.ForeignKey(Level)
    price = models.PositiveIntegerField()  # Lesson price
    salary = models.PositiveIntegerField(default=0)
    commission_percentage = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('region', 'ability', 'level')

    def __str__(self):
        return '%s,%s,%s => %d' % (
                self.region, self.ability, self.level, self.price)

    @property
    def grade(self):
        return self.ability.grade

    @property
    def subject(self):
        return self.ability.subject


class Profile(BaseModel):
    """
    For extending the system class: User
    """
    MALE = 'm'
    FEMALE = 'f'
    UNKNOWN = 'u'
    GENDER_CHOICES = (
        (FEMALE, '女'),
        (MALE, '男'),
        (UNKNOWN, '未知'),
    )

    user = models.OneToOneField(User)
    phone = models.CharField(max_length=20, default='', db_index=True)
    # deprecated: use django group instead
    # role = models.ForeignKey(Role, null=True, blank=True,
    #                          on_delete=models.SET_NULL)
    gender = models.CharField(max_length=1,
                              choices=GENDER_CHOICES,
                              default=UNKNOWN,
                              )
    avatar = models.ImageField(null=True, blank=True, upload_to='avatars')
    birthday = models.DateField(blank=True, null=True, default=None)

    def __str__(self):
        return '%s (%s)' % (self.user, self.gender)

    def mask_phone(self):
        return "{before}****{after}".format(
                before=self.phone[:3], after=self.phone[-4:])

    def avatar_url(self):
        return self.avatar and self.avatar.url or ''


class Teacher(BaseModel):
    DEGREE_CHOICES = (
        ('h', '高中'),
        ('s', '专科'),
        ('b', '本科'),
        ('p', '研究生'),
    )
    TO_CHOOSE = 1
    NOT_CHOSEN = 2
    TO_INTERVIEW = 3
    INTERVIEW_OK = 4
    INTERVIEW_FAIL = 5
    STATUS_CHOICES = (
        (TO_CHOOSE, '待处理'),
        (NOT_CHOSEN, '初选淘汰'),
        (TO_INTERVIEW, '邀约面试'),
        (INTERVIEW_OK, '面试通过'),
        (INTERVIEW_FAIL, '面试失败'),
    )
    user = models.OneToOneField(User)
    name = models.CharField(max_length=200)
    degree = models.CharField(max_length=2,
                              choices=DEGREE_CHOICES,
                              )
    published = models.BooleanField(default=False)
    fulltime = models.BooleanField(default=True)
    teaching_age = models.PositiveIntegerField(default=0)
    level = models.ForeignKey(Level, null=True, blank=True,
                              on_delete=models.SET_NULL)

    experience = models.PositiveSmallIntegerField(null=True, blank=True)
    profession = models.PositiveSmallIntegerField(null=True, blank=True)
    interaction = models.PositiveSmallIntegerField(null=True, blank=True)
    video = models.FileField(null=True, blank=True, upload_to='video')
    audio = models.FileField(null=True, blank=True, upload_to='audio')

    tags = models.ManyToManyField(Tag)
    schools = models.ManyToManyField(School)
    weekly_time_slots = models.ManyToManyField('WeeklyTimeSlot')
    abilities = models.ManyToManyField('Ability')

    region = models.ForeignKey(Region, null=True, blank=True,
                               limit_choices_to={'opened': True})
    status = models.IntegerField(default=1, choices=STATUS_CHOICES)

    graduate_school = models.CharField(max_length=50, blank=True, null=True)
    introduce = models.CharField(max_length=200, blank=True, null=True)

    recommended_on_wechat = models.BooleanField(default=False)

    def __str__(self):
        return '%s %s %s' % (self.name, 'F' if self.fulltime else '',
                             'Unpublished' if not self.published else '')

    def avatar(self):
        if not hasattr(self.user, 'profile'):
            return None
        return self.user.profile.avatar or None

    def gender(self):
        if not hasattr(self.user, 'profile'):
            return None
        return self.user.profile.gender

    def subject(self):
        abilities = self.abilities.all()
        if not abilities:
            return None
        return abilities[0].subject

    def grades(self):
        abilities = self.abilities.all()
        return [ability.grade for ability in abilities]

    def grades_shortname(self):
        grades = self.grades()
        grades = list(set(x.superset if x.superset else x for x in grades))
        sort_dict = {'小学': 1, '初中': 2, '高中': 3}
        grades = sorted(grades, key=lambda x: sort_dict.get(x.name, 4))
        if len(grades) == 0:
            return ''
        if len(grades) == 1:
            return grades[0].name
        else:
            return ''.join(x.name[0] for x in grades)

    def prices(self):
        abilities = self.abilities.all()
        return Price.objects.filter(
                level=self.level, region=self.region,
                ability__in=abilities)

    def min_price(self):
        prices = list(self.prices())
        if not prices:
            return None
        return min(x.price for x in prices)

    def max_price(self):
        prices = list(self.prices())
        if not prices:
            return None
        return max(x.price for x in prices)

    def is_english_teacher(self):
        subject = self.subject()
        ENGLISH = Subject.get_english()
        return subject and (subject.id == ENGLISH.id)

    def audio_url(self):
        return self.audio and self.audio.url or ''

    def video_url(self):
        return self.video and self.video.url or ''

    def cert_verified_count(self):
        Certificate = apps.get_model('app', 'Certificate')
        if self.is_english_teacher():
            cert_types = [Certificate.ID_HELD, Certificate.ACADEMIC,
                          Certificate.TEACHING, Certificate.OTHER]
        else:
            cert_types = [Certificate.ID_HELD, Certificate.ACADEMIC,
                          Certificate.TEACHING, Certificate.ENGLISH,
                          Certificate.OTHER]
        return Certificate.objects.filter(
                teacher=self, verified=True, type__in=cert_types).distinct(
                        'type').count()

    # 获得当前审核进度
    def get_progress(self):
        if self.status in [self.TO_CHOOSE, self.NOT_CHOSEN]:
            return 1
        if self.status in [self.TO_INTERVIEW, self.INTERVIEW_FAIL]:
            return 2
        if self.status in [self.INTERVIEW_OK]:
            return 3

    # 建立审核信息
    def build_progress_info(self):
        tree = Tree()
        tree.root = Node(1)
        tree.insert_val(1, 3, 2)
        tree.insert_val(3, 4)
        tree.insert_val(4, 5)
        tree.insert_val(5, 7, 6)
        tree.insert_val(7, 8)
        tree.insert_val(8, 9)
        status_2_node = {
            self.TO_CHOOSE: 1,
            self.NOT_CHOSEN: 2,
            self.TO_INTERVIEW: 5,
            self.INTERVIEW_FAIL: 6,
            self.INTERVIEW_OK: 9
        }
        # return tree.get_path(status_2_node.get(self.INTERVIEW_OK, 1))
        # return range(1,10)
        return tree.get_path(status_2_node.get(self.status, 1))

    def safe_get_account(self):
        # 获得账户,如果没有账户就创建一个
        try:
            account = self.user.account
        except AttributeError:
            # 新建一个账户
            account = Account(user=self.user, balance=0)
            account.save()
        return account

    def longterm_available_dict(self, school):
        TimeSlot = apps.get_model('app', 'TimeSlot')

        renew_time = TimeSlot.RENEW_TIME
        traffic_time = int(TimeSlot.TRAFFIC_TIME.total_seconds()) // 60

        teacher = self
        region = school.region
        weekly_time_slots = region.weekly_time_slots.all()

        date = timezone.now() - renew_time
        occupied = TimeSlot.objects.filter(
                order__teacher=teacher, start__gte=date, deleted=False)
        occupied = [
                (x if x.transferred_from is None else x.transferred_from)
                for x in occupied]

        segtree = SegmentTree(0, 7 * 24 * 60 - 1)
        for occ in occupied:
            cur_school = occ.order.school
            occ.start = timezone.localtime(occ.start)
            occ.end = timezone.localtime(occ.end)
            start = (occ.start.weekday() * 24 * 60 + occ.start.hour * 60 +
                     occ.start.minute)

            end = (occ.end.weekday() * 24 * 60 + occ.end.hour * 60 +
                   occ.end.minute - 1)

            if cur_school.id != school.id:
                start, end = start - traffic_time, end + traffic_time
            segtree.add(start, end)

        def w2m(w, t):
            return (w - 1) * 24 * 60 + t.hour * 60 + t.minute

        data = {(s.weekday, s.start, s.end): (segtree.query_len(
            w2m(s.weekday, s.start), w2m(s.weekday, s.end) - 1) == 0)
            for s in weekly_time_slots
            }
        return data

    def is_longterm_available(self, periods, school):
        '''
        periods: [(weekday, start, end), ...]
        weekday: int (1-7)
        start: time
        end: time
        '''
        la_dict = self.longterm_available_dict(school)
        for period in periods:
            if not la_dict[period]:
                return False
        return True

    def shortterm_available_dict(self, school):
        TimeSlot = apps.get_model('app', 'TimeSlot')

        renew_time = TimeSlot.RENEW_TIME
        shortterm = TimeSlot.SHORTTERM
        traffic_time = int(TimeSlot.TRAFFIC_TIME.total_seconds()) // 60

        teacher = self
        region = school.region
        weekly_time_slots = region.weekly_time_slots.all()

        date = timezone.now()
        occupied = models.TimeSlot.objects.filter(
                order__teacher=teacher, start__gte=date - renew_time,
                end__lt=date + shortterm + renew_time, deleted=False)

        segtree = SegmentTree(0, 7 * 24 * 60 - 1)
        for occ in occupied:
            cur_school = occ.order.school
            occ.start = timezone.localtime(occ.start)
            occ.end = timezone.localtime(occ.end)
            start = (occ.start.weekday() * 24 * 60 + occ.start.hour * 60 +
                     occ.start.minute)

            end = (occ.end.weekday() * 24 * 60 + occ.end.hour * 60 +
                   occ.end.minute - 1)

            if cur_school.id != school.id:
                start, end = start - traffic_time, end + traffic_time
            segtree.add(start, end)

        def w2m(w):
            return (w.weekday - 1) * 24 * 60 + w.hour * 60 + w.minute

        data = {(s.weekday, s.start, s.end): (segtree.query_len(
            w2m(s.start), w2m(s.end) - 1) == 0)
            for s in weekly_time_slots
            }
        return data

    def is_shortterm_available(self, start, end, school):
        '''
        start: datetime
        end: datetime
        '''
        assert end > start
        assert start.weekday() == end.weekday()

        shortterm = TimeSlot.SHORTTERM
        sa_dict = self.shortterm_available_dict(school)
        date = timezone.now()

        if not (start >= date and end < date + shortterm):
            return False

        weekday = start.weekday()
        start = datetime.time(hour=start.hour, minute=start.minute)
        end = datetime.time(hour=end.hour, minute=end.minute)

        return sa_dict[(weekday, start, end)]

    # 新建一个空白老师用户
    @staticmethod
    def new_teacher()->User:
        # 新建用户
        username = random_string()[:30]
        salt = random_string()[:5]
        password = "malalaoshi"
        user = User(username=username)
        user.email = ""
        user.password = make_password(password, salt)
        user.save()
        # 创建老师身份
        profile = Profile(user=user, phone="")
        profile.save()
        teacher = Teacher(user=user)
        teacher.save()
        teacher_group = Group.objects.get(name="老师")
        user.groups.add(teacher_group)
        # 集体保存
        user.save()
        profile.save()
        teacher.save()
        ret_user = authenticate(username=username, password=password)
        return ret_user


class Highscore(BaseModel):
    """
    提分榜
    """
    teacher = models.ForeignKey(Teacher)
    name = models.CharField(max_length=200)
    increased_scores = models.IntegerField(default=0)
    school_name = models.CharField(max_length=300)
    admitted_to = models.CharField(max_length=300)

    def __str__(self):
        return '%s %s (%s => %s)' % (
                self.name, self.increased_scores, self.school_name,
                self.admitted_to)


class Achievement(BaseModel):
    """
    特殊成果
    """
    teacher = models.ForeignKey(Teacher)
    title = models.CharField(max_length=30)
    img = models.ImageField(null=True, blank=True, upload_to='achievements')

    def img_url(self):
        return self.img and self.img.url or ''


class Photo(BaseModel):
    teacher = models.ForeignKey(Teacher)
    img = models.ImageField(null=True, blank=True, upload_to='photos')
    order = models.PositiveIntegerField(default=0)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '%s img (%s)' % (
                self.teacher, 'public' if self.public else 'private')

    def img_url(self):
        return self.img and self.img.url or ''


class Certificate(BaseModel):
    """
    资质认证,身份认证用了两个记录(因为身份认证有手持照),判断是否通过认证用
    """
    ID_HELD = 1
    ID_FRONT = 2
    ACADEMIC = 3
    TEACHING = 4
    ENGLISH = 5
    OTHER = 6

    TYPE_CHOICES = (
        (ID_HELD, '身份证手持照'),
        (ID_FRONT, '身份证正面'),
        (ACADEMIC, '学历认证'),
        (TEACHING, '教师资格证'),
        (ENGLISH, '英语水平证书'),
        (OTHER, '其他资质认证'),
    )

    teacher = models.ForeignKey(Teacher)
    name = models.CharField(max_length=100)
    type = models.IntegerField(null=True, blank=True, choices=TYPE_CHOICES)
    img = models.ImageField(null=True, blank=True, upload_to='certs')
    verified = models.BooleanField()

    def __str__(self):
        return '%s, %s : %s' % (self.teacher, self.name,
                                'V' if self.verified else '')

    def img_url(self):
        return self.img and self.img.url or ''


class InterviewRecord(BaseModel):
    PENDING = 'p'
    APPROVED = 'a'
    REJECTED = 'r'
    STATUS_CHOICES = (
        (PENDING, '待认证'),
        (APPROVED, '已认证'),
        (REJECTED, '已拒绝'),
    )

    teacher = models.ForeignKey(Teacher)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True)
    review_msg = models.CharField(max_length=1000)
    status = models.CharField(max_length=1,
                              choices=STATUS_CHOICES,
                              default=PENDING)

    def __str__(self):
        return '%s by %s' % (self.teacher, self.reviewed_by)


class Account(BaseModel):
    """
    用户(老师)财务账户
    """
    user = models.OneToOneField(User)
    balance = models.PositiveIntegerField(default=0)

    @property
    def calculated_balance(self):
        AccountHistory = apps.get_model('app', 'AccountHistory')
        ret = AccountHistory.objects.filter(
                account=self, done=True).aggregate(models.Sum('amount'))
        sum = ret['amount__sum']
        return sum and sum/100 or 0

    @property
    def accumulated_income(self):
        AccountHistory = apps.get_model('app', 'AccountHistory')
        ret = AccountHistory.objects.filter(
                account=self, amount__gt=0, done=True).aggregate(
                        models.Sum('amount'))
        sum = ret['amount__sum']
        return sum and sum/100 or 0

    @property
    def anticipated_income(self):
        """
        预计收入, 完成未来所有课时后将会得到的金额
        :return:
        """
        # TODO: 预计收入
        return 0

    def __str__(self):
        return '%s : %d' % (self.user, self.balance)


class BankCard(BaseModel):
    bank_name = models.CharField(max_length=100)
    card_number = models.CharField(max_length=100, unique=True)
    account = models.ForeignKey(Account)

    def __str__(self):
        return '%s %s (%s)' % (self.bank_name, self.card_number,
                               self.account.user)


class BankCodeInfo(BaseModel):
    org_code = models.CharField(max_length=30)
    bank_name = models.CharField(max_length=30)
    card_name = models.CharField(max_length=30)
    card_type = models.CharField(max_length=2)
    card_number_length = models.PositiveIntegerField()
    bin_code_length = models.PositiveIntegerField()
    bin_code = models.CharField(max_length=30)

    def __str__(self):
        return '%s, %s, %s (%s)' % (self.bank_name, self.card_name,
                                    self.card_type, self.bin_code)


class AccountHistory(BaseModel):
    account = models.ForeignKey(Account)
    amount = models.IntegerField()
    bankcard = models.ForeignKey(BankCard, null=True, blank=True)
    submit_time = models.DateTimeField()
    done = models.BooleanField(default=False)
    done_by = models.ForeignKey(User, related_name='processed_withdraws',
                                null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    comment = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return '%s %s : %s' % (self.account.user, self.amount,
                               'D' if self.done else '')


class Feedback(BaseModel):
    user = models.ForeignKey(User, null=True, blank=True)
    contact = models.CharField(max_length=30)
    content = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '%s %s %s' % (self.user, self.contact, self.created_at)


class Parent(BaseModel):
    user = models.OneToOneField(User)

    student_name = models.CharField(max_length=50)
    student_school_name = models.CharField(max_length=100, default='')

    def recent_orders(self):
        one_month_before = timezone.now() - datetime.timedelta(days=90)
        return self.order_set.filter(created_at__gt=one_month_before)

    def __str__(self):
        return "{child_name}'s parent [{parent_name}]".format(
                child_name=self.student_name, parent_name=self.user.username)


class CouponRule(BaseModel):
    """
    奖学金使用规则
    """
    content = models.CharField(max_length=50)


class CouponGenerator(BaseModel):
    """
    奖学金生成规则
    """
    activated = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    validated_start = models.DateTimeField(
            null=False, blank=False, default=timezone.now)
    expired_at = models.DateTimeField(
            null=False, blank=False, default=timezone.now)
    amount = models.PositiveIntegerField()
    mini_course_count = models.PositiveSmallIntegerField(default=0)


class Coupon(BaseModel):
    parent = models.ForeignKey(Parent, null=True, blank=True)
    name = models.CharField(max_length=50)
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    validated_start = models.DateTimeField(
            null=False, blank=False, default=timezone.now)
    expired_at = models.DateTimeField(
            null=False, blank=False, default=timezone.now)
    used = models.BooleanField()
    mini_course_count = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return '%s, %s (%s) %s' % (self.parent, self.amount, self.expired_at,
                                   'D' if self.used else '')


class WeeklyTimeSlot(BaseModel):
    weekday = models.PositiveIntegerField()  # 1 - 7
    start = models.TimeField()  # [0:00 - 24:00)
    end = models.TimeField()

    class Meta:
        unique_together = ('weekday', 'start', 'end')

    def __str__(self):
        return '%s from %s to %s' % (self.weekday, self.start, self.end)

    @classproperty
    def DAILY_TIME_SLOTS(cls):
        return [
                dict(start=item.start, end=item.end) for item in
                cls.objects.filter(weekday=1).order_by('start')]


class OrderManager(models.Manager):
    def create(self, parent, teacher, school, grade, subject, hours, coupon):
        ability = grade.ability_set.filter(subject=subject)[0]

        price = teacher.region.price_set.get(
                ability=ability, level=teacher.level).price

        discount_amount = coupon.amount if coupon is not None else 0

        total = price * hours - discount_amount

        order_id = orderid()

        order = super(OrderManager, self).create(
                parent=parent, teacher=teacher, school=school, grade=grade,
                subject=subject, price=price, hours=hours,
                total=total, coupon=coupon, order_id=order_id)

        order.save()
        return order

    def _weekly_date_to_minutes(self, date):
        return date.weekday() * 24 * 60 + date.hour * 60 + date.minute

    def _delta_minutes(self, weekly_ts, cur_min):
        return (
                (weekly_ts.weekday - 1) * 24 * 60 + weekly_ts.start.hour * 60 +
                weekly_ts.start.minute - cur_min + 7 * 24 * 60) % (7 * 24 * 60)

    def concrete_timeslots(self, hours, weekly_time_slots):
        grace_time = TimeSlot.GRACE_TIME
        date = timezone.now() + grace_time
        date = date.replace(second=0, microsecond=0)
        date += datetime.timedelta(minutes=1)

        cur_min = self._weekly_date_to_minutes(date)
        weekly_time_slots.sort(
                key=lambda x: self._delta_minutes(x, cur_min))

        n = len(weekly_time_slots)
        h = hours
        i = 0
        ans = []
        while h > 0:
            weekly_ts = weekly_time_slots[i % n]
            start = date + datetime.timedelta(
                    minutes=self._delta_minutes(weekly_ts, cur_min)
                    ) + datetime.timedelta(days=7 * (i // n))

            end = start + datetime.timedelta(
                    minutes=(weekly_ts.end.hour - weekly_ts.start.hour) * 60 +
                    weekly_ts.end.minute - weekly_ts.start.minute)

            ans.append(dict(start=start, end=end))
            i = i + 1
            h = h - 1
        return ans

    def get_order_timeslots(self, order, check_conflict=True):
        weekly_time_slots = list(order.weekly_time_slots.all())
        periods = [(s.weekday, s.start, s.end) for s in weekly_time_slots]
        if check_conflict:
            school = order.school
            teacher = order.teacher

            if not teacher.is_longterm_available(periods, school):
                raise TimeSlotConflict()
        return self.concrete_timeslots(order.hours, weekly_time_slots)

    def allocate_timeslots(self, order, force=False):
        TimeSlot = apps.get_model('app', 'TimeSlot')
        if order.status == 'p' and not force:
            raise TimeSlotConflict()

        name = '/teacher_%d' % order.teacher.id
        semaphore = posix_ipc.Semaphore(
                name, flags=posix_ipc.O_CREAT, initial_value=1)
        semaphore.acquire()
        try:
            timeslots = self.get_order_timeslots(order)
            for ts in timeslots:
                timeslot = TimeSlot(
                        order=order, start=ts['start'], end=ts['end'])
                timeslot.save()

        except Exception as e:
            raise e
        finally:
            semaphore.release()
        return timeslots


class Order(BaseModel):
    PENDING = 'u'
    PAID = 'p'
    CANCELED = 'd'

    # REFUND 表示已经退费成功的订单
    # todo: 订单的退费成功状态只应该在审核通过时设置, 其他地方不应操作
    REFUND = "r"
    STATUS_CHOICES = (
        (PENDING, '待付款'),
        (PAID, '已付款'),
        (CANCELED, '已取消'),
        (REFUND, '退费')
    )

    objects = OrderManager()

    parent = models.ForeignKey(Parent, null=True, blank=True)
    teacher = models.ForeignKey(Teacher)
    school = models.ForeignKey(School)
    grade = models.ForeignKey(Grade)
    subject = models.ForeignKey(Subject)
    coupon = models.ForeignKey(Coupon, null=True, blank=True)
    weekly_time_slots = models.ManyToManyField(WeeklyTimeSlot)

    price = models.PositiveIntegerField()
    hours = models.PositiveIntegerField()
    order_id = models.CharField(max_length=20, default=orderid, unique=True)
    total = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=2,
                              choices=STATUS_CHOICES,
                              default=PENDING, )

    def __str__(self):
        return '%s %s %s %s %s : %s' % (
                self.school, self.parent, self.teacher, self.grade,
                self.subject, self.total)

    def fit_statistical(self):
        # 主要用于FirstPage中
        return self.status == self.PAID

    def fit_school_time(self):
        # 主要用于学校课程表中
        return self.status == self.PAID

    def enum_timeslot(self, handler):
        for one_timeslot in self.timeslot_set.filter(deleted=False):
            handler(one_timeslot)


class OrderRefundRecord(BaseModel):
    PENDING = 'u'
    APPROVED = 'a'
    REJECTED = 'r'
    # 这里的文字描述是以申请者的角度, 审核者应该分别为("待处理", "已退费", "已驳回")
    STATUS_CHOICES = (
        (PENDING, '退费审核中'),
        (APPROVED, '退费成功'),
        (REJECTED, '退费被驳回')
    )

    status = models.CharField(max_length=2,
                              choices=STATUS_CHOICES,
                              default=PENDING, )

    order = models.ForeignKey(Order)
    reason = models.CharField(max_length=100, default="退费原因", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(User)

    def approve_refund(self):
        if self.status == OrderRefundRecord.PENDING:
            self.status = OrderRefundRecord.APPROVED
            # todo: 订单的退费成功状态只应该在这一处操作
            self.order.status = Order.REFUND
            self.order.save()
            self.save()
        return self.status

    def reject_refund(self):
        if self.status == OrderRefundRecord.PENDING:
            self.status = OrderRefundRecord.REJECTED
            self.save()
        return self.status


class Charge(BaseModel):
    order = models.ForeignKey(Order, null=True, blank=True)
    ch_id = models.CharField(max_length=40, unique=True)
    created = models.DateTimeField(null=True, blank=True)
    livemode = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)
    refunded = models.BooleanField(default=False)
    app = models.CharField(max_length=40)
    channel = models.CharField(max_length=10)
    order_no = models.CharField(max_length=20)
    client_ip = models.CharField(max_length=50)
    amount = models.IntegerField(default=0)
    amount_settle = models.IntegerField(default=0)
    currency = models.CharField(max_length=5)
    subject = models.CharField(max_length=20)
    body = models.CharField(max_length=200)
    extra = models.TextField()
    time_paid = models.DateTimeField(null=True, blank=True)
    time_expire = models.DateTimeField(null=True, blank=True)
    time_settle = models.DateTimeField(null=True, blank=True)
    transaction_no = models.CharField(max_length=50)
    amount_refunded = models.IntegerField(default=0)
    failure_code = models.CharField(max_length=10)
    failure_msg = models.CharField(max_length=30)
    metadata = models.CharField(max_length=50)
    credential = models.TextField()
    description = models.CharField(max_length=50)


class TimeSlotComplaint(BaseModel):
    content = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(User, null=True, blank=True)

    def __str__(self):
        return '%s' % (self.content)


class TimeSlotAttendance(BaseModel):
    NORMAL = 'a'
    ABSENT = 'b'
    LATE10 = 'c'
    LATE10_30 = 'd'
    LATE30 = 'e'
    TYPE_CHOICES = (
        (LATE10, '10分钟内'),
        (LATE10_30, '10-30分钟'),
        (LATE30, '30分钟以上'),
        (ABSENT, '缺勤'),
        (NORMAL, '正常出勤'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(User, null=True, blank=True)
    record_type = models.CharField(max_length=1,
                                   choices=TYPE_CHOICES,
                                   default=NORMAL)

    def __str__(self):
        return '%s' % (self.get_record_type_display())


class Comment(BaseModel):
    # 评分, 评分低于3分是差评
    score = models.PositiveIntegerField()
    content = models.CharField(max_length=500)
    # 回复
    reply = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '%s : %d' % (self.pk, self.score)

    def is_bad_comment(self):
        # 差评
        if self.score < 3:
            return True
        return False

    def is_mediu_evaluation(self):
        # 中评
        if 2 < self.score < 5:
            return True
        return False

    def is_high_praise(self):
        # 好评
        if self.score == 5:
            return True
        return False


class TimeSlot(BaseModel):
    TRAFFIC_TIME = datetime.timedelta(hours=1)
    RENEW_TIME = datetime.timedelta(hours=2)
    SHORTTERM = datetime.timedelta(days=7)
    GRACE_TIME = datetime.timedelta(days=2)

    order = models.ForeignKey(Order)
    start = models.DateTimeField()
    end = models.DateTimeField()

    confirmed_by = models.ForeignKey(Parent, null=True, blank=True)
    transferred_from = models.ForeignKey(
            'TimeSlot', related_name='trans_to_set', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(User, null=True, blank=True)

    comment = models.OneToOneField(Comment, null=True, blank=True)
    complaint = models.OneToOneField(TimeSlotComplaint, null=True, blank=True)
    attendance = models.OneToOneField(
            TimeSlotAttendance, null=True, blank=True)

    deleted = models.BooleanField(default=False)

    def __str__(self):
        return '<%s> from %s' % (self.pk, self.start, )

    def is_complete(self, given_time=make_aware(datetime.datetime.now())):
        # 对于给定的时间,课程是否结束
        if self.end < given_time:
            return True
        return False

    def is_waiting(self, given_time):
        # 对于给定时间,课程是否处于等待
        if given_time < self.start:
            return True
        return False

    def is_running(self, given_time):
        # 对于给定时间,课程是否处于上课中
        if self.start < given_time < self.end:
            return True
        return False

    @property
    def trans_to_time(self):
        if self.deleted and self.trans_to_set.exists():
            return self.trans_to_set.first().start

    @property
    def is_transfered(self):
        # 判断为已经被调课状态
        if self.deleted and self.trans_to_set.exists():
            return True
        return False

    @property
    def is_suspended(self):
        # 判断为被停课状态
        if self.deleted and not self.trans_to_set.exists():
            return True
        return False

    @property
    def subject(self):
        return self.order.subject

    @property
    def is_passed(self):
        return timezone.now() > self.end


class Message(BaseModel):
    SYSTEM = 's'
    FINANCE = 'f'
    COURSE = 'c'
    AUDIT = 'a'
    COMMENT = 'm'
    TYPE_CHOICES = (
        (SYSTEM, '系统消息'),
        (FINANCE, '收入消息'),
        (COURSE, '课程消息'),
        (AUDIT, '审核消息'),
        (COMMENT, '评论消息'),
    )

    SMS = 's'
    MAIL = 'm'
    NOTIFICATION = 'n'
    VIA_CHOICES = (
        (SMS, '短信'),
        (MAIL, '邮件'),
        (NOTIFICATION, '通知栏提醒'),
    )

    to = models.ForeignKey(User)
    viewed = models.BooleanField()
    deleted = models.BooleanField()
    title = models.CharField(max_length=100)
    content = models.CharField(max_length=1000)
    _type = models.CharField(max_length=1,
                             choices=TYPE_CHOICES,
                             )
    via = models.CharField(max_length=1,
                           choices=VIA_CHOICES,
                           )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '%s, %s, to %s, %s' % (
                self.get__type_display(), self.get_via_display(),
                self.to, self.title)


class Checkcode(BaseModel):
    phone = models.CharField(max_length=20, unique=True)
    checkcode = models.CharField(max_length=30)
    updated_at = models.DateTimeField(auto_now_add=True)
    verify_times = models.PositiveIntegerField(default=0)
    resend_at = models.DateTimeField(blank=True, null=True, default=None)

    @staticmethod
    def verify_sms(phone, code):
        try:
            Checkcode.objects.get(phone=phone, checkcode=code)
            return True
        except Checkcode.DoesNotExist:
            return False
